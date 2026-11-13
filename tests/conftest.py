"""测试不读取本地 Logfire 凭据，也不向远程导出遥测。"""

from pathlib import Path

import pytest
from pg_database import pg_database
from starlette.testclient import TestClient


@pytest.fixture(autouse=True)
def authenticated_clients(monkeypatch):
    from auth_helpers import TEST_PASSWORD, authenticate

    monkeypatch.setenv("JWT_SECRET_KEY", "offline-signing-key-for-tests-only-32")
    monkeypatch.setenv("INITIAL_USERNAME", "offline")
    monkeypatch.setenv("INITIAL_PASSWORD", TEST_PASSWORD)
    enter = TestClient.__enter__

    def authenticated_enter(self):
        result = enter(self)
        authenticate(self)
        return result

    monkeypatch.setattr(TestClient, "__enter__", authenticated_enter)


@pytest.fixture(autouse=True)
def offline_logfire(monkeypatch):
    # 环境变量优先于 Settings 加载的本地 .env。
    monkeypatch.setenv("LOGFIRE_TOKEN", "")
    monkeypatch.setenv("LOGFIRE_SEND_TO_LOGFIRE", "false")


@pytest.fixture
def app_factory(monkeypatch):
    from app import main as app

    def create(settings=None, agent=None):
        from dbos._dbos import _get_or_create_dbos_registry

        _get_or_create_dbos_registry().instance_info_map.clear()
        with monkeypatch.context() as patch:
            if settings is not None:
                patch.setattr(app, "Settings", lambda: settings)
            if agent is not None:
                from pydantic_ai.capabilities import CombinedCapability
                from pydantic_ai.durable_exec.dbos import DBOSDurability

                from app.chat.streams import record_events

                # 使用官方 FunctionModel；在 worker 启动前注册实际测试模型和工具。
                model = agent._get_model_outside_run()
                agent.model = model
                root = agent.root_capability.visit_and_replace(
                    lambda cap: None if isinstance(cap, DBOSDurability) else cap
                )
                durability = DBOSDurability(
                    name="offline-travel",
                    event_stream_handler=record_events,
                    model_step_config={"preemptible": True},
                    models={"offline": model},
                    parallel_execution_mode="sequential",
                ).for_agent(agent)
                agent._root_capability = CombinedCapability(
                    [*([root] if root else []), durability]
                )
                patch.setattr(app, "create_agent", lambda settings: agent)
            return app.create_app()

    return create


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def store_factory():
    from contextlib import AsyncExitStack

    from app.db.travel import TravelStore

    async with AsyncExitStack() as stack:

        async def create(database):
            url = pg_database(database) if isinstance(database, Path) else database
            return await stack.enter_async_context(TravelStore(url))

        yield create


@pytest.fixture(autouse=True)
def postgres_settings(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", pg_database(tmp_path / "default"))
    monkeypatch.delenv("DBOS_DATABASE_URL", raising=False)


@pytest.fixture(scope="session", autouse=True)
def cleanup_postgres():
    from pg_database import drop_test_databases

    yield
    drop_test_databases()
