"""浏览器测试专用：真实 FastAPI/SQLite/流协议，使用离线模型。"""

import os
from pathlib import Path

import anyio
from pydantic_ai import Agent
from pydantic_ai.messages import ToolReturnPart, UserPromptPart
from pydantic_ai.models.function import DeltaToolCall, FunctionModel

from app import create_app as create_backend
from settings import Settings
from trip import TripStore


async def stream(messages, info):
    if not any(isinstance(p, ToolReturnPart) for p in messages[-1].parts):
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


agent = Agent(FunctionModel(stream_function=stream), deps_type=TripStore)


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
        ),
        agent,
    )
