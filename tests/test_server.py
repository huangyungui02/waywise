"""验证真实 PostgreSQL 与官方适配器在多轮、重启和错误场景下的行为。"""

import pytest
from pg_database import pg_database
from pydantic_ai.direct import model_request
from pydantic_ai.messages import ModelResponse, TextPart, UserPromptPart
from pydantic_ai.models.function import DeltaToolCall, FunctionModel
from starlette.testclient import TestClient
from test_app import configured as configured  # noqa: PLC0414 — 导出 pytest fixture。
from test_arrangements import itinerary as itinerary  # noqa: PLC0414 — 导出 pytest fixture。

from app import agent as agent_module
from app.models.arrangements import TravelArrangements
from app.settings import Settings


@pytest.mark.parametrize("fails", [False, True])
def test_first_reply_names_conversation_without_thinking(
    app_factory, configured, monkeypatch, tmp_path, fails
):
    from app.db import conversations

    calls = []

    def title(messages, info):
        return ModelResponse(parts=[TextPart("成都至四姑娘山双人游")])

    async def naming(model, messages, **kwargs):
        calls.append((messages, kwargs))
        if fails:
            raise RuntimeError("本地标题服务失败")
        return await model_request(FunctionModel(title), messages, **kwargs)

    async def reply(messages, info):
        yield "请告诉我出发日期。"

    monkeypatch.setattr(conversations, "model_request", naming)
    agent = agent_module.create_agent()
    with (
        agent.override(model=FunctionModel(stream_function=reply)),
        TestClient(
            app_factory(
                Settings(database_url=pg_database(tmp_path / "naming.db")),
                agent,
            )
        ) as client,
    ):
        created = client.post("/api/conversations").json()
        fields = {"id", "title", "outcome", "updated_at"}
        assert set(created) == fields
        assert created["updated_at"].endswith("Z")
        assert client.get("/api/conversations").json() == [created]
        cid = created["id"]
        prompt = "这次旅行的想法：\n出发城市：成都\n目的城市：四姑娘山\n同行人数：2"
        client.post(f"/api/conversations/{cid}/chat", json=request(prompt))
        detail = client.get(f"/api/conversations/{cid}").json()
        assert detail["summary"]["title"] == (
            prompt[:40] if fails else "成都至四姑娘山双人游"
        )
        assert set(detail["summary"]) == fields
        assert detail["summary"]["updated_at"].endswith("Z")
        assert detail["summary"]["outcome"] == "completed"
        assert calls[0][1]["model_settings"]["extra_body"] == {"enable_thinking": False}
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


def test_history_restart_and_server_owned_context(app_factory, configured, tmp_path):
    settings = Settings(database_url=pg_database(tmp_path / "travel.db"))
    seen = []

    async def model(messages, info):
        seen.append(messages)
        yield "可以，先聊聊需求。"

    agent = agent_module.create_agent()
    with agent.override(model=FunctionModel(stream_function=model)):
        with TestClient(app_factory(settings, agent)) as client:
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
        with TestClient(app_factory(settings, agent)) as client:
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


@pytest.mark.anyio
async def test_confirmed_arrangements_persists_and_deletes(
    app_factory, configured, tmp_path, itinerary, store_factory
):
    settings = Settings(database_url=pg_database(tmp_path / "travel.db"))
    agent = agent_module.create_agent()
    count = 0

    async def model(messages, info):
        nonlocal count
        count += 1
        if count == 1:
            import json

            yield {
                0: DeltaToolCall(
                    name="present_arrangements",
                    json_args=json.dumps(itinerary),
                    tool_call_id="proposal-1",
                )
            }
        else:
            yield "交通住宿已确认。"

    with agent.override(model=FunctionModel(stream_function=model)):
        with TestClient(app_factory(settings, agent)) as client:
            cid = client.post("/api/conversations").json()["id"]
            response = client.post(
                f"/api/conversations/{cid}/chat", json=request("确认安排")
            )
            assert "present_arrangements" in response.text
            pending = client.get(f"/api/conversations/{cid}").json()
            assert pending["arrangements"] is None
            assert (
                pending["pending_arrangements"]["transports"][0]["arrival_station"]
                == "杭州东"
            )
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
                == 200
            )
            response = client.post(
                f"/api/conversations/{cid}/chat", json=request("继续规划")
            )
            assert "交通住宿已确认" in response.text
            data = client.get(f"/api/conversations/{cid}").json()
            assert data["arrangements"]["transports"][0]["number"] == "G123"
            assert "present_arrangements" in str(data["messages"])
        assert (
            await (
                await store_factory(database=settings.database_url.get_secret_value())
            ).arrangements.get(cid)
        ) == TravelArrangements.model_validate(itinerary)

        with TestClient(app_factory(settings, agent)) as client:
            restored = client.get(f"/api/conversations/{cid}").json()
            assert restored["arrangements"] == data["arrangements"]
            assert restored["summary"]["outcome"] == "completed"
            assert "交通住宿已确认" in str(restored["messages"])
            client.delete(f"/api/conversations/{cid}")
        assert (
            await (
                await store_factory(database=settings.database_url.get_secret_value())
            ).arrangements.get(cid)
        ) is None


def test_failed_run_retains_question_and_marks_interrupted(
    app_factory, configured, tmp_path
):
    settings = Settings(database_url=pg_database(tmp_path / "travel.db"))

    async def broken(messages, info):
        raise RuntimeError("测试中断")
        yield ""

    agent = agent_module.create_agent()
    with (
        agent.override(model=FunctionModel(stream_function=broken)),
        TestClient(app_factory(settings, agent)) as client,
    ):
        cid = client.post("/api/conversations").json()["id"]
        response = client.post(
            f"/api/conversations/{cid}/chat", json=request("查询杭州")
        )
        assert "error" in response.text
        history = client.get(f"/api/conversations/{cid}").json()
        assert "查询杭州" in str(history["messages"])
        assert history["summary"]["outcome"] == "failed"
        assert client.delete(f"/api/conversations/{cid}").status_code == 204


@pytest.mark.anyio
async def test_legacy_interrupted_conversation_can_continue(
    app_factory, configured, tmp_path, store_factory
):
    from pydantic_ai.messages import ModelRequest, UserPromptPart

    settings = Settings(database_url=pg_database(tmp_path / "legacy.db"))
    store = (
        await store_factory(settings.database_url.get_secret_value())
    ).conversations
    created = await store.create()
    conversation = await store.load(created.id)
    await store.save_messages(
        conversation, [ModelRequest(parts=[UserPromptPart("旧的旅行需求")])], "running"
    )

    async def model(messages, info):
        yield "继续旧的旅行。"

    agent = agent_module.create_agent()
    with (
        agent.override(model=FunctionModel(stream_function=model)),
        TestClient(app_factory(settings, agent)) as client,
    ):
        detail = client.get(f"/api/conversations/{created.id}").json()
        assert detail["summary"]["outcome"] == "cancelled"
        assert detail["recovery"] is None
        assert "旧的旅行需求" in str(detail["messages"])
        response = client.post(
            f"/api/conversations/{created.id}/chat", json=request("继续")
        )
        assert "继续旧的旅行" in response.text


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("get", "", None),
        ("patch", "", {"title": "杭州"}),
        ("delete", "", None),
        ("delete", "/products/missing", None),
        ("post", "/proposals/missing/confirm", None),
        ("get", "/chat/stream", None),
        ("post", "/chat/stop", None),
        ("post", "/chat", request("去杭州")),
    ],
)
def test_conversation_dependencies_reject_missing_conversation(
    app_factory, configured, tmp_path, method, path, body
):
    backend = app_factory(Settings(database_url=pg_database(tmp_path / "missing.db")))
    with TestClient(backend) as client:
        response = client.request(
            method, f"/api/conversations/missing{path}", json=body
        )
        assert response.status_code == 404
        assert response.json() == {"detail": "会话不存在"}
