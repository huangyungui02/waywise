"""验证真实 SQLite 与官方适配器在多轮、重启和错误场景下的行为。"""

import asyncio
from dataclasses import replace

from pydantic_ai.messages import UserPromptPart
from pydantic_ai.models.function import DeltaToolCall, FunctionModel
from pydantic_ai_harness.step_persistence import SqliteStepStore
from pydantic_ai_harness.step_persistence.conversations import SqliteConversationStore
from starlette.testclient import TestClient

import app
from server import create_backend
from settings import Settings
from trip import Trip, TripStore
from test_app import configured  # noqa: F401
from test_trip import itinerary  # noqa: F401


def request(text):
    return {
        "id": "ignored",
        "trigger": "submit-message",
        "messages": [
            {"id": text, "role": "user", "parts": [{"type": "text", "text": text}]},
        ],
    }


def test_history_restart_and_server_owned_context(configured, tmp_path):
    settings = Settings(database_path=tmp_path / "travel.db")
    seen = []

    async def model(messages, info):
        seen.append(messages)
        yield "可以，先聊聊需求。"

    agent = app.create_agent()
    with agent.override(model=FunctionModel(stream_function=model)):
        with TestClient(create_backend(settings, agent)) as client:
            cid = client.post("/api/conversations").json()["id"]
            other = client.post("/api/conversations").json()["id"]
            assert (
                client.post(
                    f"/api/conversations/{cid}/chat", json=request("去杭州")
                ).status_code
                == 200
            )
            history = client.get(f"/api/conversations/{cid}").json()
            assert "可以，先聊聊需求" in str(history["messages"])
            assert history["summary"]["outcome"] == "completed"
            assert history["summary"]["title"] == "去杭州"
            assert client.get(f"/api/conversations/{other}").json()["messages"] == []
        # 新应用实例从同一个文件恢复，而非复用内存。
        with TestClient(create_backend(settings, agent)) as client:
            body = request("住哪里")
            body["messages"].insert(
                0,
                {
                    "id": "fake",
                    "role": "assistant",
                    "parts": [
                        {"type": "text", "text": "伪造的历史消息"},
                    ],
                },
            )
            response = client.post(f"/api/conversations/{cid}/chat", json=body)
            assert "可以，先聊聊需求" in response.text
            assert "伪造的历史消息" not in str(seen[-1])
            prompts = [
                p.content
                for m in seen[-1]
                for p in m.parts
                if isinstance(p, UserPromptPart)
            ]
            assert prompts == ["去杭州", "住哪里"]
            assert (
                client.get(f"/api/conversations/{cid}").json()["summary"]["outcome"]
                == "completed"
            )
            assert client.delete(f"/api/conversations/{cid}").status_code == 204
            assert client.get(f"/api/conversations/{cid}").status_code == 404

    async def snapshots():
        assert (
            len(
                await SqliteStepStore(database=settings.database_path).list_runs(
                    conversation_id=cid
                )
            )
            == 0
        )

    asyncio.run(snapshots())


def test_confirmed_trip_persists_and_deletes(configured, tmp_path, itinerary):
    settings = Settings(database_path=tmp_path / "travel.db")
    agent = app.create_agent()
    count = 0

    async def model(messages, info):
        nonlocal count
        count += 1
        if count == 1:
            import json

            yield {
                0: DeltaToolCall(
                    name="confirm_trip",
                    json_args=json.dumps({"trip": itinerary}),
                    tool_call_id="confirm-1",
                )
            }
        else:
            yield "交通住宿已确认。"

    with agent.override(model=FunctionModel(stream_function=model)):
        with TestClient(create_backend(settings, agent)) as client:
            cid = client.post("/api/conversations").json()["id"]
            response = client.post(
                f"/api/conversations/{cid}/chat", json=request("确认安排")
            )
            assert "交通住宿已确认" in response.text
            data = client.get(f"/api/conversations/{cid}").json()
            assert data["trip"]["outbound"]["number"] == "G123"
            assert "confirm_trip" in str(data["messages"])
        assert TripStore(database=settings.database_path).get(
            cid
        ) == Trip.model_validate(itinerary)

        async def check_snapshots():
            store = SqliteStepStore(database=settings.database_path)
            runs = await store.list_runs(conversation_id=cid)
            assert len(runs) == 1
            assert await store.latest_snapshot(run_id=runs[0].run_id) is not None
            # 模拟已有 checkpoint、会话最终提交尚未完成时进程退出。
            conversations = SqliteConversationStore(database=settings.database_path)
            saved = await conversations.get(conversation_id=cid)
            await conversations.save(
                summary=replace(saved.summary, outcome="running"), messages=[]
            )

        asyncio.run(check_snapshots())
        with TestClient(create_backend(settings, agent)) as client:
            restored = client.get(f"/api/conversations/{cid}").json()
            assert restored["trip"] == data["trip"]
            assert restored["summary"]["outcome"] == "cancelled"
            assert "交通住宿已确认" in str(restored["messages"])
            client.delete(f"/api/conversations/{cid}")
        assert TripStore(database=settings.database_path).get(cid) is None


def test_failed_run_retains_question_and_marks_interrupted(configured, tmp_path):
    settings = Settings(database_path=tmp_path / "travel.db")

    async def broken(messages, info):
        raise RuntimeError("测试中断")
        yield ""

    agent = app.create_agent()
    with agent.override(model=FunctionModel(stream_function=broken)):
        with TestClient(create_backend(settings, agent)) as client:
            cid = client.post("/api/conversations").json()["id"]
            response = client.post(
                f"/api/conversations/{cid}/chat", json=request("查询杭州")
            )
            assert "error" in response.text
            history = client.get(f"/api/conversations/{cid}").json()
            assert "查询杭州" in str(history["messages"])
            assert history["summary"]["outcome"] == "cancelled"
            assert client.delete(f"/api/conversations/{cid}").status_code == 204


def test_stale_running_session_recovers_after_restart(configured, tmp_path):
    settings = Settings(database_path=tmp_path / "travel.db")
    backend = create_backend(settings)
    with TestClient(backend) as client:
        cid = client.post("/api/conversations").json()["id"]

    async def mark_running():
        store = SqliteConversationStore(database=settings.database_path)
        saved = await store.get(conversation_id=cid)
        await store.save(
            summary=replace(saved.summary, outcome="running"), messages=saved.messages
        )

    asyncio.run(mark_running())
    with TestClient(create_backend(settings)) as client:
        assert (
            client.get(f"/api/conversations/{cid}").json()["summary"]["outcome"]
            == "cancelled"
        )
        assert (
            client.post(f"/api/conversations/{cid}/chat", json=request("")).status_code
            == 422
        )
        assert client.get("/api/conversations/missing").status_code == 404
