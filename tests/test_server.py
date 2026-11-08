"""验证真实 SQLite 与官方适配器在多轮、重启和错误场景下的行为。"""

import asyncio
from dataclasses import replace

import pytest
from pydantic_ai.direct import model_request
from pydantic_ai.messages import ModelResponse, TextPart
from pydantic_ai.messages import UserPromptPart
from pydantic_ai.models.function import DeltaToolCall, FunctionModel
from pydantic_ai_harness.step_persistence import SqliteStepStore
from pydantic_ai_harness.step_persistence.conversations import SqliteConversationStore
from starlette.testclient import TestClient
from test_app import configured  # noqa: F401
from test_trip import itinerary  # noqa: F401

import agent as agent_module
from app import create_app
from settings import Settings
from trip import Trip, TripStore


@pytest.mark.parametrize("fails", [False, True])
def test_first_reply_names_conversation_without_thinking(
    configured, monkeypatch, tmp_path, fails
):
    import app

    calls = []

    def title(messages, info):
        return ModelResponse(parts=[TextPart("成都至四姑娘山双人游")])

    async def naming(model, messages, **kwargs):
        calls.append((messages, kwargs))
        if fails:
            raise RuntimeError("本地标题服务失败")
        return await model_request(model, messages, **kwargs)

    async def reply(messages, info):
        yield "请告诉我出发日期。"

    monkeypatch.setattr(app, "model_request", naming)
    agent = agent_module.create_agent()
    with agent.override(model=FunctionModel(stream_function=reply)):
        with TestClient(
            create_app(
                Settings(database_path=tmp_path / "naming.db"),
                agent,
                title_model=FunctionModel(title),
            )
        ) as client:
            cid = client.post("/api/conversations").json()["id"]
            prompt = "这次旅行的想法：\n出发城市：成都\n目的城市：四姑娘山\n同行人数：2"
            client.post(f"/api/conversations/{cid}/chat", json=request(prompt))
            detail = client.get(f"/api/conversations/{cid}").json()
            assert detail["summary"]["title"] == (
                prompt[:40] if fails else "成都至四姑娘山双人游"
            )
            assert detail["summary"]["outcome"] == "completed"
            assert calls[0][1]["model_settings"]["extra_body"] == {
                "enable_thinking": False
            }
            client.post(f"/api/conversations/{cid}/chat", json=request("下周出发"))
            assert len(calls) == 1
            assert (
                client.get(f"/api/conversations/{cid}").json()["summary"]["title"]
                == detail["summary"]["title"]
            )


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

    agent = agent_module.create_agent()
    with agent.override(model=FunctionModel(stream_function=model)):
        with TestClient(create_app(settings, agent)) as client:
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
        with TestClient(create_app(settings, agent)) as client:
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
    agent = agent_module.create_agent()
    count = 0

    async def model(messages, info):
        nonlocal count
        count += 1
        if count == 1:
            import json

            yield {
                0: DeltaToolCall(
                    name="present_trip",
                    json_args=json.dumps(itinerary),
                    tool_call_id="proposal-1",
                )
            }
        else:
            yield "交通住宿已确认。"

    with agent.override(model=FunctionModel(stream_function=model)):
        with TestClient(create_app(settings, agent)) as client:
            cid = client.post("/api/conversations").json()["id"]
            response = client.post(
                f"/api/conversations/{cid}/chat", json=request("确认安排")
            )
            assert "present_trip" in response.text
            pending = client.get(f"/api/conversations/{cid}").json()
            assert pending["trip"] is None
            assert pending["pending_trip"]["destination"] == "杭州"
            assert (
                client.post(
                    f"/api/conversations/{cid}/proposals/old/confirm"
                ).status_code
                == 409
            )
            assert (
                client.post(
                    f"/api/conversations/{cid}/proposals/proposal-1/confirm"
                ).status_code
                == 200
            )
            assert (
                client.post(
                    f"/api/conversations/{cid}/proposals/proposal-1/confirm"
                ).status_code
                == 409
            )
            response = client.post(
                f"/api/conversations/{cid}/chat", json=request("继续规划")
            )
            assert "交通住宿已确认" in response.text
            data = client.get(f"/api/conversations/{cid}").json()
            assert data["trip"]["outbound"]["number"] == "G123"
            assert "present_trip" in str(data["messages"])
        assert TripStore(database=settings.database_path).get(
            cid
        ) == Trip.model_validate(itinerary)

        async def check_snapshots():
            store = SqliteStepStore(database=settings.database_path)
            runs = await store.list_runs(conversation_id=cid)
            assert len(runs) == 2
            assert await store.latest_snapshot(run_id=runs[0].run_id) is not None
            # 模拟已有 checkpoint、会话最终提交尚未完成时进程退出。
            conversations = SqliteConversationStore(database=settings.database_path)
            saved = await conversations.get(conversation_id=cid)
            await conversations.save(
                summary=replace(saved.summary, outcome="running"), messages=[]
            )

        asyncio.run(check_snapshots())
        with TestClient(create_app(settings, agent)) as client:
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

    agent = agent_module.create_agent()
    with agent.override(model=FunctionModel(stream_function=broken)):
        with TestClient(create_app(settings, agent)) as client:
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
    backend = create_app(settings)
    with TestClient(backend) as client:
        cid = client.post("/api/conversations").json()["id"]

    async def mark_running():
        store = SqliteConversationStore(database=settings.database_path)
        saved = await store.get(conversation_id=cid)
        await store.save(
            summary=replace(saved.summary, outcome="running"), messages=saved.messages
        )

    asyncio.run(mark_running())
    with TestClient(create_app(settings)) as client:
        assert (
            client.get(f"/api/conversations/{cid}").json()["summary"]["outcome"]
            == "cancelled"
        )
        assert (
            client.post(f"/api/conversations/{cid}/chat", json=request("")).status_code
            == 422
        )
        assert client.get("/api/conversations/missing").status_code == 404
