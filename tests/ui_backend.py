"""浏览器测试专用：真实 FastAPI/SQLite/流协议，使用离线模型。"""

import os
from pathlib import Path

import anyio
from pydantic_ai import Agent, RunContext, ToolOutput
from pydantic_ai.messages import UserPromptPart
from pydantic_ai.models.function import DeltaToolCall, FunctionModel

from app import create_app as create_backend
from settings import Settings
from trip import Trip, TripStore
from agent import present_trip
from test_trip import ITINERARY


async def stream(messages, info):
    prompt = next(
        p.content
        for m in reversed(messages)
        for p in m.parts
        if isinstance(p, UserPromptPart)
    )
    if isinstance(messages[-1].parts[-1], UserPromptPart):
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
    return create_backend(
        Settings(
            _env_file=None,
            DASHSCOPE_API_KEY="test-key",
            AMAP_MAPS_API_KEY="test-map-key",
            database_path=Path(os.environ["UI_TEST_DATABASE"]),
            logfire_token="",
        ),
        agent,
    )
