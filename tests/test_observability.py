"""使用真实 Logfire/OTel 内存导出器验证链路与正文采集边界。"""

import json

import logfire
import pytest
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from pydantic_ai import Agent
from pydantic_ai.messages import ModelResponse, TextPart, ToolReturnPart
from pydantic_ai.models.function import DeltaToolCall, FunctionModel
from starlette.testclient import TestClient

import app
from settings import Settings
from trip import TripStore


@pytest.mark.parametrize("include_content", [False, True])
def test_request_agent_tool_trace_and_content(
    app_factory, monkeypatch, tmp_path, include_content
):
    exporter = InMemorySpanExporter()
    configure = logfire.configure

    def configure_offline(**kwargs):
        assert kwargs.pop("token") == "test-write-token"
        assert kwargs.pop("send_to_logfire") is True
        return configure(
            **kwargs,
            send_to_logfire=False,
            metrics=False,
            additional_span_processors=[SimpleSpanProcessor(exporter)],
        )

    monkeypatch.setattr(app.logfire, "configure", configure_offline)

    async def stream(messages, info):
        if not any(isinstance(part, ToolReturnPart) for part in messages[-1].parts):
            yield {
                0: DeltaToolCall(
                    name="call_flyai",
                    json_args=json.dumps({"query": "private-tool-argument"}),
                    tool_call_id="flyai-test",
                )
            }
        else:
            yield "private-model-response"

    agent = Agent(
        FunctionModel(
            lambda messages, info: ModelResponse(parts=[TextPart("测试旅行")]),
            stream_function=stream,
        ),
        deps_type=TripStore,
    )

    @agent.tool_plain
    def call_flyai(query: str) -> str:
        """离线飞猪工具替身。"""
        return "private-tool-result"

    settings = Settings(
        _env_file=None,
        DASHSCOPE_API_KEY="test-key",
        AMAP_MAPS_API_KEY="test-map-key",
        database_path=tmp_path / "travel.db",
        logfire_token="test-write-token",
        logfire_include_content=include_content,
    )
    assert "test-write-token" not in repr(settings)
    with TestClient(
        app_factory(
            settings,
            agent,
        )
    ) as client:
        conversation_id = client.post("/api/conversations").json()["id"]
        body = {
            "id": conversation_id,
            "trigger": "submit-message",
            "messages": [
                {
                    "id": "user-1",
                    "role": "user",
                    "parts": [{"type": "text", "text": "private-user-message"}],
                }
            ],
        }
        response = client.post(f"/api/conversations/{conversation_id}/chat", json=body)
        assert response.status_code == 200
        assert "private-model-response" in response.text
        # 无效请求也不能通过 FastAPI 参数/校验错误泄露正文。
        client.post(
            f"/api/conversations/{conversation_id}/chat",
            json={"messages": "private-invalid-body"},
        )
        before = len(exporter.get_finished_spans())
        assert client.get("/api/health").status_code == 200
        assert len(exporter.get_finished_spans()) == before

    spans = exporter.get_finished_spans()
    tool_span = next(
        span
        for span in spans
        if span.attributes and span.attributes.get("gen_ai.tool.name") == "call_flyai"
    )
    chat_span = next(
        span
        for span in spans
        if span.name == "POST /api/conversations/{conversation_id}/chat"
        and span.attributes
        and span.attributes.get("http.status_code") == 200
    )
    assert tool_span.context.trace_id == chat_span.context.trace_id
    assert tool_span.parent is not None
    telemetry = str([span.attributes for span in spans])
    for content in (
        "private-user-message",
        "private-tool-argument",
        "private-tool-result",
        "private-model-response",
    ):
        assert (content in telemetry) is include_content
    assert "private-invalid-body" not in telemetry


def test_no_token_does_not_configure_logfire(app_factory, monkeypatch, tmp_path):
    def unexpected(**kwargs):
        pytest.fail("未配置 Token 时不应初始化 Logfire")

    monkeypatch.setattr(app.logfire, "configure", unexpected)
    settings = Settings(
        _env_file=None,
        DASHSCOPE_API_KEY="test-key",
        AMAP_MAPS_API_KEY="test-map-key",
        logfire_token="",
        database_path=tmp_path / "travel.db",
    )
    with TestClient(
        app_factory(settings, Agent("test", deps_type=TripStore))
    ) as client:
        assert client.get("/api/health").status_code == 200


def test_local_logfire_token_is_not_loaded_in_tests(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("LOGFIRE_TOKEN=test-local-token\n")
    settings = Settings(
        _env_file=env_file,
        DASHSCOPE_API_KEY="test-key",
        AMAP_MAPS_API_KEY="test-map-key",
    )
    assert settings.logfire_token.get_secret_value() == ""
