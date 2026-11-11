"""在真实 DBOS/SQLite 中验证执行历史过期和业务历史独立保存。"""

from datetime import UTC, datetime, timedelta

from dbos import DBOS
from pydantic_ai import Agent
from pydantic_ai.models.function import FunctionModel
from starlette.testclient import TestClient
from test_server import request

from app.chat.retention import clean_workflow_history
from app.settings import Settings


@DBOS.workflow()
async def waiting_workflow():
    await DBOS.recv_async(timeout_seconds=3600)


def test_retention_preserves_chat_and_active_workflows(app_factory, tmp_path):
    async def model(messages, info):
        yield "旅行建议"

    settings = Settings(
        _env_file=None,
        DASHSCOPE_API_KEY="test",
        AMAP_MAPS_API_KEY="test",
        database_path=tmp_path / "travel.db",
    )
    backend = app_factory(settings, Agent(FunctionModel(stream_function=model)))
    with TestClient(backend) as client:
        schedule = DBOS.get_schedule("workflow-history-retention")
        assert schedule["context"] == 7
        cid = client.post("/api/conversations").json()["id"]
        client.post(f"/api/conversations/{cid}/chat", json=request("出游"))
        before = client.get(f"/api/conversations/{cid}").json()
        assert before["summary"]["outcome"] == "completed"
        run_id = before["recovery"]["run_id"]

        active = DBOS.start_workflow(waiting_workflow)

        def clean(when):
            handle = DBOS.start_workflow(clean_workflow_history, when, 7)
            handle.get_result()

        clean(datetime.now(UTC))
        assert DBOS.get_workflow_status(run_id) is not None
        clean(datetime.now(UTC) + timedelta(days=8))
        assert DBOS.get_workflow_status(run_id) is None
        assert DBOS.get_workflow_status(f"{run_id}/generation") is None
        assert DBOS.get_workflow_status(active.workflow_id) is not None

        # 官方删除 API 同时清除了流，且业务历史仍可正常读取并继续聊天。
        import sqlite3

        with sqlite3.connect(tmp_path / "dbos.sqlite") as conn:
            assert conn.execute("SELECT count(*) FROM streams").fetchone()[0] == 0
        after = client.get(f"/api/conversations/{cid}").json()
        assert after["messages"] == before["messages"]
        assert after["summary"]["outcome"] == "completed"
        assert after["recovery"] is None
        assert client.get(f"/api/conversations/{cid}/chat/stream").status_code == 204
        response = client.post(f"/api/conversations/{cid}/chat", json=request("继续"))
        assert "旅行建议" in response.text
        DBOS.send(active.workflow_id, True)
        active.get_result()
