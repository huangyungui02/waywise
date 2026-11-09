"""浏览器测试专用：真实 FastAPI/SQLite/流协议，使用离线模型。"""

import os
from pathlib import Path
from unittest.mock import patch

import anyio
from pydantic_ai import Agent, RunContext, ToolOutput
from pydantic_ai.messages import (
    ModelResponse,
    NativeToolCallPart,
    NativeToolReturnPart,
    TextPart,
    UserPromptPart,
)
from pydantic_ai.models.function import DeltaThinkingPart, DeltaToolCall, FunctionModel

from app import create_app as create_backend
from settings import Settings
from trip import Trip, TripStore
from agent import present_trip
from test_trip import ITINERARY

search_replies: dict[str, anyio.Event] = {}


async def stream(messages, info):
    prompt = next(
        p.content
        for m in reversed(messages)
        for p in m.parts
        if isinstance(p, UserPromptPart)
    )
    if isinstance(messages[-1].parts[-1], UserPromptPart):
        if prompt == "失败恢复测试":
            yield "失败前已经生成的建议。"
            raise RuntimeError("离线模型失败")
        if str(prompt).startswith("搜索恢复测试"):
            finished = search_replies[str(prompt)] = anyio.Event()
            yield {0: DeltaThinkingPart(content="首次思考，不应展示")}
            yield "好的，继续。"
            yield "最后核实回程班车的班次，确认后即可锁定方案。"
            yield {
                1: NativeToolCallPart(
                    "web_search", {"query": "回程班车"}, tool_call_id="search-test"
                )
            }
            yield {
                2: NativeToolReturnPart(
                    "web_search", {"status": "completed"}, tool_call_id="search-test"
                )
            }
            yield {3: DeltaThinkingPart(content="搜索后的思考，不应展示")}
            try:
                await finished.wait()
            finally:
                search_replies.pop(str(prompt), None)
            yield {
                4: DeltaToolCall(
                    name="present_trip",
                    json_args=Trip.model_validate(ITINERARY).model_dump_json(),
                    tool_call_id="search-proposal",
                )
            }
            return
        if prompt == "后台测试":
            yield "正在后台整理旅行…"
            await anyio.sleep(3)
            yield "后台旅行建议已完成。"
            return
        if prompt == "思考测试":
            yield {0: DeltaThinkingPart(content="这是不应展示的思考内容")}
            await anyio.sleep(2)
            yield "旅行建议已整理好。"
            await anyio.sleep(2)
            yield "接下来一起确定出发日期。"
            return
        if str(prompt) in ("展示方案", "换酒店"):
            plan = Trip.model_validate(ITINERARY)
            if prompt == "换酒店":
                plan.stays[0].hotel = "新的测试酒店"
            yield {
                0: DeltaToolCall(
                    name="present_trip",
                    json_args=plan.model_dump_json(),
                    tool_call_id="proposal-new"
                    if prompt == "换酒店"
                    else "proposal-first",
                )
            }
            return
        if prompt == "确认方案":
            yield {
                0: DeltaToolCall(
                    name="confirm_trip", json_args="{}", tool_call_id="confirm-test"
                )
            }
            return
    if "已确认卡片" in str(prompt) or prompt == "确认方案":
        yield "交通住宿已确认，现在开始每日行程规划。"
        return
    if isinstance(messages[-1].parts[-1], UserPromptPart):
        yield {
            0: DeltaToolCall(
                name="current_time", json_args="{}", tool_call_id="clock-test"
            )
        }
    else:
        prompt = next(
            p.content
            for m in reversed(messages)
            for p in m.parts
            if isinstance(p, UserPromptPart)
        )
        if "停止测试" in str(prompt):
            yield "正在安排这次旅行…"
            await anyio.sleep(30)
        yield f"收到你的旅行想法：{prompt}。"
        yield "\n\n请告诉我具体出发日期，我们先选交通和住宿。"


agent = Agent(
    FunctionModel(stream_function=stream),
    deps_type=TripStore,
    output_type=[str, ToolOutput(present_trip, name="present_trip")],
    end_strategy="early",
)


@agent.tool
def confirm_trip(ctx: RunContext[TripStore]) -> dict:
    """浏览器测试的确认入口；使用真实 SQLite 确认逻辑。"""
    assert ctx.conversation_id is not None
    return {"trip": ctx.deps.confirm(ctx.conversation_id).model_dump(mode="json")}


@agent.tool_plain
def current_time() -> str:
    """浏览器测试的本地时间工具。"""
    return "2026-11-06 10:00"


def create_app():
    def title(messages, info):
        prompt = str(
            next(
                p.content
                for m in messages
                for p in m.parts
                if isinstance(p, UserPromptPart)
            )
        )
        return ModelResponse(
            parts=[
                TextPart(
                    prompt
                    if not prompt.startswith("这次旅行的想法：")
                    else "四姑娘山旅行"
                )
            ]
        )

    agent.model = FunctionModel(title, stream_function=stream)
    settings = Settings(
        _env_file=None,
        DASHSCOPE_API_KEY="test-key",
        AMAP_MAPS_API_KEY="test-map-key",
        database_path=Path(os.environ["UI_TEST_DATABASE"]),
        logfire_token="",
    )
    with (
        patch("app.Settings", return_value=settings),
        patch("app.create_agent", return_value=agent),
    ):
        backend = create_backend()

    @backend.post("/api/__test/finish-search")
    async def finish_search(prompt: str):
        search_replies[prompt].set()

    return backend
