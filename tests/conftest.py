"""测试不读取本地 Logfire 凭据，也不向远程导出遥测。"""

import pytest


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
            return await stack.enter_async_context(TravelStore(database))

        yield create
