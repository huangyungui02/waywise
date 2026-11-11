"""浏览器测试专用：真实 FastAPI/SQLite/流协议，使用离线模型。"""

import json
import os
from pathlib import Path
from unittest.mock import patch

import anyio
from dbos import DBOS
from pydantic_ai import Agent, RunContext, ToolOutput
from pydantic_ai.durable_exec.dbos import DBOSDurability
from pydantic_ai.messages import (
    ModelResponse,
    NativeToolCallPart,
    NativeToolReturnPart,
    TextPart,
    UserPromptPart,
)
from pydantic_ai.models.function import DeltaThinkingPart, DeltaToolCall, FunctionModel
from test_arrangements import ITINERARY, MULTI_ITINERARY

from app.agent import present_arrangements, present_products
from app.db.travel import TravelStore
from app.main import create_app as create_backend
from app.models.arrangements import TravelArrangements
from app.settings import Settings
from app.streams import record_events

search_replies: dict[str, anyio.Event] = {}


async def stream(messages, info):
    prompt = next(
        p.content
        for m in reversed(messages)
        for p in m.parts
        if isinstance(p, UserPromptPart)
    )
    if isinstance(messages[-1].parts[-1], UserPromptPart):
        if prompt == "商品卡片测试":
            yield "综合预算，我推荐下面这家酒店："
            yield {
                0: DeltaToolCall(
                    name="present_products",
                    json_args=json.dumps(
                        {
                            "products": [
                                {
                                    "name": "测试酒店",
                                    "description": "近景区，适合两晚住宿。",
                                    "price": "12月1日 ¥94 起 / 房 / 晚",
                                    "purchase_url": "https://example.com/hotel",
                                    "image_url": "https://example.com/hotel.png",
                                },
                                {
                                    "name": "测试门票",
                                    "description": "游览日期及库存请在预订页面核实。",
                                    "purchase_url": "https://example.com/ticket",
                                },
                            ]
                        }
                    ),
                    tool_call_id="products-test",
                )
            }
            return
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
                    name="present_arrangements",
                    json_args=TravelArrangements.model_validate(
                        ITINERARY
                    ).model_dump_json(),
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
        if str(prompt) in (
            "展示方案",
            "换酒店",
            "多城市方案",
            "自驾轮渡方案",
            "打车轮渡方案",
        ):
            plan = TravelArrangements.model_validate(
                MULTI_ITINERARY if prompt == "多城市方案" else ITINERARY
            )
            if prompt in ("自驾轮渡方案", "打车轮渡方案"):
                plan.transports[0].type = (
                    "taxi" if prompt == "打车轮渡方案" else "drive"
                )
                plan.transports[0].number = None
                plan.transports[0].purchase_url = None
                plan.transports[1].type = "ferry"
                plan.transports[1].number = None
            if prompt == "换酒店":
                plan.stays[0].hotel = "新的测试酒店"
            yield {
                0: DeltaToolCall(
                    name="present_arrangements",
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
                    name="confirm_arrangements",
                    json_args="{}",
                    tool_call_id="confirm-test",
                )
            }
            return
    if prompt == "商品卡片测试":
        yield "你更倾向这家酒店，还是希望再比较一下？"
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
    deps_type=TravelStore,
    output_type=[str, ToolOutput(present_arrangements, name="present_arrangements")],
    end_strategy="early",
    name="offline-ui",
    capabilities=[
        DBOSDurability(
            event_stream_handler=record_events,
            model_step_config={"preemptible": True},
            parallel_execution_mode="sequential",
        )
    ],
)


agent.tool(present_products)


@agent.tool
@DBOS.step()
async def confirm_arrangements(ctx: RunContext[TravelStore]) -> dict:
    """浏览器测试的确认入口；使用真实 SQLite 确认逻辑。"""
    assert ctx.conversation_id is not None
    return {
        "arrangements": (
            await ctx.deps.arrangements.confirm(ctx.conversation_id)
        ).model_dump(mode="json")
    }


@agent.tool_plain
@DBOS.step()
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

    agent.model.function = title
    settings = Settings(
        _env_file=None,
        DASHSCOPE_API_KEY="test-key",
        AMAP_MAPS_API_KEY="test-map-key",
        database_path=Path(os.environ["UI_TEST_DATABASE"]),
        logfire_token="",
    )
    with (
        patch("app.main.Settings", return_value=settings),
        patch("app.main.create_agent", return_value=agent),
    ):
        backend = create_backend()

    @backend.post("/api/__test/finish-search")
    async def finish_search(prompt: str):
        search_replies[prompt].set()

    return backend
