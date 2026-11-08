"""测试不读取本地 Logfire 凭据，也不向远程导出遥测。"""

import pytest


@pytest.fixture(autouse=True)
def offline_logfire(monkeypatch):
    # 环境变量优先于 Settings 加载的本地 .env。
    monkeypatch.setenv("LOGFIRE_TOKEN", "")
    monkeypatch.setenv("LOGFIRE_SEND_TO_LOGFIRE", "false")
