"""验证官方组件之间的接线；不访问真实模型或旅游服务。"""

import asyncio
import json
import subprocess

import httpx2
import pytest
from pydantic_ai.capabilities import AbstractCapability
from pydantic_ai.messages import (
    CompactionPart,
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.models.function import DeltaToolCall, FunctionModel
from pydantic_ai.toolsets import FunctionToolset
from starlette.testclient import TestClient

import agent as agent_module
from settings import Settings


@pytest.fixture
def configured(monkeypatch):
    import replies
    from pydantic_ai.direct import model_request

    async def local_title_request(model, messages, **kwargs):
        return await model_request(
            FunctionModel(
                lambda messages, info: ModelResponse(
                    parts=[
                        TextPart(
                            str(
                                next(
                                    p.content
                                    for m in messages
                                    for p in m.parts
                                    if isinstance(p, UserPromptPart)
                                )
                            )
                        )
                    ]
                )
            ),
            messages,
            **kwargs,
        )

    monkeypatch.setattr(replies, "model_request", local_title_request)
    monkeypatch.setenv("AMAP_MAPS_API_KEY", "test-key")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "test-dashscope-key")
    monkeypatch.setenv("TRAVEL_MODEL", "qwen3.8-flash")
    monkeypatch.setenv("PYDANTIC_AI_NO_BANNER", "1")

    class LocalMaps(AbstractCapability):
        def get_toolset(self):
            tools = FunctionToolset()

            @tools.tool_plain
            def amap_route() -> str:
                return "车站到酒店：公交 30 分钟（测试数据）"

            return tools

    monkeypatch.setattr(agent_module, "MCP", lambda *args, **kwargs: LocalMaps())


def test_missing_map_key(monkeypatch):
    monkeypatch.delenv("AMAP_MAPS_API_KEY", raising=False)
    with pytest.raises(ValueError, match="AMAP_MAPS_API_KEY"):
        agent_module.Settings(_env_file=None)


def test_skill_reference_cli_and_maps(configured, monkeypatch, tmp_path):
    # 使用本地 CLI 替身，验证完整的 Skill -> 文档 -> call_flyai 调用链。
    cli = tmp_path / "flyai"
    cli.write_text('#!/bin/sh\nprintf \'{"data":{"itemList":[]},"status":0}\\n\'\n')
    cli.chmod(0o755)
    monkeypatch.setenv("PATH", str(tmp_path) + ":/usr/bin:/bin")
    calls = iter(
        [
            ("load_capability", {"id": "flyai"}),
            ("read_file", {"path": "flyai/references/search-train.md"}),
            (
                "call_flyai",
                {
                    "args": [
                        "search-train",
                        "--origin",
                        "上海",
                        "--destination",
                        "杭州",
                        "--dep-date",
                        "2026-12-01",
                    ]
                },
            ),
            ("amap_route", {}),
        ]
    )

    def model(messages, info):
        call = next(calls, None)
        if call:
            return ModelResponse(parts=[ToolCallPart(*call)])
        return ModelResponse(parts=[TextPart("测试完成")])

    agent = agent_module.create_agent()
    with agent.override(model=FunctionModel(model)):
        result = agent.run_sync("检查旅行工具链")
    results = [
        p
        for m in result.all_messages()
        for p in m.parts
        if isinstance(p, ToolReturnPart)
    ]
    assert len(results) == 4
    assert "loaded" in str(results[0].content)
    assert "FlyAI — Travel" in repr(result.all_messages())
    assert "--origin" in str(results[1].content)
    assert '"status":0' in str(results[2].content)
    assert "30 分钟" in str(results[3].content)


@pytest.mark.parametrize(
    "tool,args",
    [
        ("read_file", {"path": "../.env"}),
        ("call_flyai", {"args": ["config", "set", "FLYAI_API_KEY", "unexpected"]}),
        ("call_flyai", {"args": []}),
    ],
)
def test_tool_constraints(configured, tool, args):
    requests = 0

    def model(messages, info):
        nonlocal requests
        requests += 1
        if requests == 1:
            return ModelResponse(parts=[ToolCallPart(tool, args)])
        assert any(
            isinstance(p, ToolReturnPart) and p.outcome == "retried"
            for p in messages[-1].parts
        )
        return ModelResponse(parts=[TextPart("已拒绝")])

    agent = agent_module.create_agent()
    with agent.override(model=FunctionModel(model)):
        assert agent.run_sync("检查工具限制").output == "已拒绝"


@pytest.mark.parametrize("outcome", ["failure", "timeout", "missing"])
def test_flyai_execution_errors(configured, monkeypatch, outcome):
    def execute(command, **kwargs):
        assert command == ["flyai", "search-hotel", "--query", "杭州; echo unexpected"]
        assert kwargs["timeout"] == 60
        if outcome == "timeout":
            raise subprocess.TimeoutExpired(command, 60)
        if outcome == "missing":
            raise FileNotFoundError("flyai")
        return subprocess.CompletedProcess(command, 2, "原始输出", "查询失败")

    monkeypatch.setattr(agent_module.subprocess, "run", execute)
    requests = 0

    def model(messages, info):
        nonlocal requests
        requests += 1
        assert "run_command" not in {tool.name for tool in info.function_tools}
        if requests == 1:
            return ModelResponse(
                parts=[
                    ToolCallPart(
                        "call_flyai",
                        {"args": ["search-hotel", "--query", "杭州; echo unexpected"]},
                    )
                ]
            )
        result = next(
            part.content
            for part in messages[-1].parts
            if isinstance(part, ToolReturnPart)
        )
        if outcome == "failure":
            assert result == {
                "returncode": 2,
                "stdout": "原始输出",
                "stderr": "查询失败",
            }
        else:
            assert result["returncode"] is None
            assert result["stderr"]
        return ModelResponse(parts=[TextPart("已说明查询失败")])

    agent = agent_module.create_agent()
    with agent.override(model=FunctionModel(model)):
        assert agent.run_sync("查询酒店").output == "已说明查询失败"


def test_web_endpoints(app_factory, configured, tmp_path):

    settings = Settings(database_path=tmp_path / "test.db")
    with TestClient(app_factory(settings), base_url="http://127.0.0.1") as client:
        assert client.get("/api/health").status_code == 200
        response = client.get("/api/conversations")
        assert response.status_code == 200
        assert response.json() == []


def test_ios_cors(app_factory, configured, tmp_path):
    settings = Settings(
        database_path=tmp_path / "test.db",
        cors_origins=["capacitor://localhost"],
    )
    with TestClient(app_factory(settings)) as client:
        for method in ["GET", "POST", "PATCH", "DELETE"]:
            response = client.options(
                "/api/conversations",
                headers={
                    "Origin": "capacitor://localhost",
                    "Access-Control-Request-Method": method,
                    "Access-Control-Request-Headers": "content-type",
                },
            )
            assert response.status_code == 200
            assert (
                response.headers["access-control-allow-origin"]
                == "capacitor://localhost"
            )
        response = client.get(
            "/api/conversations", headers={"Origin": "capacitor://localhost"}
        )
        assert response.json() == []
        assert (
            response.headers["access-control-allow-origin"] == "capacitor://localhost"
        )
        response = client.options(
            "/api/conversations",
            headers={
                "Origin": "https://other.example",
                "Access-Control-Request-Method": "POST",
            },
        )
        assert response.status_code == 400
        assert "access-control-allow-origin" not in response.headers


def test_web_allows_more_than_50_model_requests(app_factory, configured, tmp_path):
    requests = 0

    async def stream_model(messages, info):
        nonlocal requests
        requests += 1
        if requests <= 50:
            yield {
                0: DeltaToolCall(
                    name="current_time", json_args="{}", tool_call_id=f"call-{requests}"
                )
            }
        else:
            yield "超过50次请求后正常完成"

    agent = agent_module.create_agent()

    with agent.override(model=FunctionModel(stream_function=stream_model)):
        with TestClient(
            app_factory(Settings(database_path=tmp_path / "test.db"), agent),
            base_url="http://127.0.0.1",
        ) as client:
            conversation_id = client.post("/api/conversations").json()["id"]
            response = client.post(
                f"/api/conversations/{conversation_id}/chat",
                json={
                    "id": conversation_id,
                    "trigger": "submit-message",
                    "messages": [
                        {
                            "id": "user-1",
                            "role": "user",
                            "parts": [{"type": "text", "text": "测试请求上限"}],
                        }
                    ],
                },
            )
    assert response.status_code == 200
    assert "超过50次请求后正常完成" in response.text
    assert requests == 51


def test_settings_dotenv_and_environment(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "DASHSCOPE_API_KEY=file-secret\nAMAP_MAPS_API_KEY=file-map-key\n"
        "TRAVEL_MODEL=qwen3.8-flash\nFLYAI_API_KEY=file-flyai-key\n"
    )
    for name in [
        "DASHSCOPE_API_KEY",
        "AMAP_MAPS_API_KEY",
        "TRAVEL_MODEL",
        "FLYAI_API_KEY",
    ]:
        monkeypatch.delenv(name, raising=False)
    settings = Settings(_env_file=env_file)
    assert settings.dashscope_api_key.get_secret_value() == "file-secret"
    assert settings.flyai_api_key.get_secret_value() == "file-flyai-key"
    assert "file-secret" not in repr(settings)
    monkeypatch.setenv("DASHSCOPE_API_KEY", "env-secret")
    assert (
        Settings(_env_file=env_file).dashscope_api_key.get_secret_value()
        == "env-secret"
    )


@pytest.mark.parametrize("streaming", [False, True])
def test_bailian_native_tools_request(configured, monkeypatch, streaming):
    """真实适配器 + HTTP Mock：原生搜索与函数工具共存，普通/流式响应均可读。"""
    provider_class = agent_module.AlibabaProvider
    captured = []
    message = {
        "id": "msg_test",
        "type": "message",
        "role": "assistant",
        "status": "completed",
        "content": [{"type": "output_text", "text": "测试完成", "annotations": []}],
    }
    response = {
        "id": "resp_test",
        "object": "response",
        "created_at": 1793836800,
        "model": "qwen3.8-flash",
        "status": "completed",
        "error": None,
        "output": [message],
        "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
    }

    def respond(request):
        captured.append(json.loads(request.content))
        assert str(request.url).endswith("/compatible-mode/v1/responses")
        assert captured[-1]["stream"] is streaming
        if not streaming:
            return httpx2.Response(200, json=response)
        events = [
            {
                "type": "response.created",
                "response": {**response, "output": [], "status": "in_progress"},
            },
            {
                "type": "response.output_item.added",
                "output_index": 0,
                "item": {**message, "content": [], "status": "in_progress"},
            },
            {
                "type": "response.content_part.added",
                "output_index": 0,
                "item_id": "msg_test",
                "content_index": 0,
                "part": {"type": "output_text", "text": "", "annotations": []},
            },
            {
                "type": "response.output_text.delta",
                "output_index": 0,
                "item_id": "msg_test",
                "content_index": 0,
                "delta": "测试完成",
            },
            {"type": "response.output_item.done", "output_index": 0, "item": message},
            {"type": "response.completed", "response": response},
        ]
        data = "".join(
            "data: " + json.dumps({**event, "sequence_number": i}) + "\n\n"
            for i, event in enumerate(events)
        )
        return httpx2.Response(
            200, text=data, headers={"content-type": "text/event-stream"}
        )

    async def run():
        async with httpx2.AsyncClient(
            transport=httpx2.MockTransport(respond)
        ) as client:
            monkeypatch.setattr(
                agent_module,
                "AlibabaProvider",
                lambda **kwargs: provider_class(
                    **kwargs,
                    http_client=client,
                ),
            )
            agent = agent_module.create_agent()
            if streaming:
                async with agent.run_stream("测试网页工具配置") as result:
                    assert await result.get_output() == "测试完成"
            else:
                assert (await agent.run("测试网页工具配置")).output == "测试完成"

    asyncio.run(run())
    body = captured[0]
    assert body["model"] == "qwen3.8-flash"
    assert body["reasoning"]["effort"] == "medium"
    assert {t["type"] for t in body["tools"]} == {"web_search", "function"}
    assert {t["name"] for t in body["tools"] if t["type"] == "function"} >= {
        "load_capability",
        "read_file",
        "call_flyai",
        "amap_route",
        "current_time",
        "confirm_trip",
        "present_trip",
    }
    assert "confirmed_trip" not in {t.get("name") for t in body["tools"]}
    assert "x-anthropic-billing-header" not in str(body)


def test_auto_compaction_persists_and_resumes(configured, monkeypatch, tmp_path):
    from pydantic_ai_harness.step_persistence.conversations import (
        ConversationSummary,
        SqliteConversationStore,
    )

    monkeypatch.setenv("COMPACT_MAX_TOKENS", "2000")
    agent = agent_module.create_agent()
    requests = []
    summary = "上海往返杭州，两人预算3000元，酒店未购买，等待确认方案。"

    async def respond(messages, info):
        requests.append(messages)
        return ModelResponse(parts=[TextPart(summary)])

    async def stream(messages, info):
        requests.append(messages)
        yield summary

    history = []
    for i in range(20):
        history.extend(
            [
                ModelRequest(parts=[UserPromptPart(f"需求{i}：" + "旅行偏好" * 100)]),
                ModelResponse(parts=[TextPart("已了解需求。")]),
            ]
        )
    history.append(ModelRequest(parts=[UserPromptPart("最近需求：酒店未购买")]))

    async def run():
        store = SqliteConversationStore(database=tmp_path / "history.db")
        with agent.override(model=FunctionModel(respond, stream_function=stream)):
            result = await agent.run("继续安排", message_history=history)
            compacted = result.all_messages()
            assert len(compacted) < len(history)
            assert any(
                isinstance(part, CompactionPart) and part.content == summary
                for message in compacted
                for part in message.parts
            )
            assert any(
                isinstance(part, UserPromptPart)
                and part.content == "最近需求：酒店未购买"
                for message in compacted
                for part in message.parts
            )
            await store.save(
                summary=ConversationSummary(
                    id="compact-test", title="杭州旅行", workspace=str(tmp_path)
                ),
                messages=compacted,
            )
            saved = await store.get(conversation_id="compact-test")
            resumed = await agent.run("酒店还没买", message_history=saved.messages)
            assert resumed.output == summary
            assert any(
                isinstance(part, CompactionPart) and part.content == summary
                for message in requests[-1]
                for part in message.parts
            )

    asyncio.run(run())
