"""测试不读取本地 Logfire 凭据，也不向远程导出遥测。"""

import pytest


@pytest.fixture(autouse=True)
def offline_logfire(monkeypatch):
    # 环境变量优先于 Settings 加载的本地 .env。
    monkeypatch.setenv("LOGFIRE_TOKEN", "")
    monkeypatch.setenv("LOGFIRE_SEND_TO_LOGFIRE", "false")


@pytest.fixture(autouse=True)
def offline_redis(monkeypatch):
    from fakeredis import FakeServer
    from fakeredis.aioredis import FakeRedis

    from stream_backend import LocalStreams

    monkeypatch.setattr("app.main.StreamBackend", LocalStreams)
    server = FakeServer()
    monkeypatch.setattr(
        "app.main.Redis.from_url",
        lambda *args, **kwargs: FakeRedis(server=server, decode_responses=True),
    )
    return server


def pytest_addoption(parser):
    parser.addoption(
        "--redis-url", default=None, help="显式启用真实 Redis Streams 联调"
    )


@pytest.fixture
def app_factory(monkeypatch):
    from app import main as app

    def create(settings=None, agent=None):
        with monkeypatch.context() as patch:
            if settings is not None:
                patch.setattr(app, "Settings", lambda: settings)
            if agent is not None:
                patch.setattr(app, "create_agent", lambda settings: agent)
            return app.create_app()

    return create
