"""旅行 Agent：使用 PydanticAI 官方工具集成。"""

import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Annotated
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from pydantic import Field
from pydantic_ai import Agent, ModelRetry, RunContext, ToolOutput
from pydantic_ai.capabilities import MCP, LocalWorkspace, WebSearch
from pydantic_ai.models.openai import OpenAIResponsesModel, OpenAIResponsesModelSettings
from pydantic_ai.providers.alibaba import AlibabaProvider
from pydantic_ai_harness import FileSystem, Skills
from pydantic_ai_harness.compaction import SummarizingCompaction, drain_summary_events

from app.db.travel import TravelStore
from app.models.arrangements import TravelArrangements
from app.models.products import Product
from app.settings import ROOT, Settings


async def present_products(
    ctx: RunContext[TravelStore],
    products: Annotated[list[Product], Field(min_length=1)],
) -> list[Product]:
    """在当前叙述位置展示已查到的酒店、门票、大巴等商品，并保存到本次旅行的备选清单；火车票和机票用文字展示。

    先查询并核实商品，使用真实预订链接和对应图片，无可靠图片或价格时留空。
    同一旅行内相同预订链接更新已有备选，日期、房型和班次等信息保留在介绍或价格说明中。
    展示前用简短文字引出推荐，之后继续比较或询问偏好，正文不再重复图片和链接。
    保存备选不代表用户已选定、确认或购买，不结束本轮咨询。
    """
    assert ctx.conversation_id is not None
    await ctx.deps.products.save(ctx.conversation_id, products)
    return products


async def present_arrangements(
    ctx: RunContext[TravelStore], arrangements: TravelArrangements
) -> TravelArrangements:
    """提交选定的完整的各段交通和住宿，以卡片展示并结束本轮，等待用户确认。

    提交前核实各段路线衔接、酒店位置和全部日期。
    预计抵达时间需有依据并提前向用户说明；购买状态以用户陈述为准。
    校验失败时修正方案后重新提交，成功后等待用户确认或提出修改。
    """
    if issues := arrangements.issues():
        raise ModelRetry("；".join(issues))
    assert ctx.conversation_id is not None and ctx.tool_call_id is not None
    await ctx.deps.arrangements.present(
        ctx.conversation_id, arrangements, ctx.tool_call_id
    )
    return arrangements


def create_agent(
    settings: Settings | None = None,
) -> Agent[TravelStore, str | TravelArrangements]:
    settings = settings or Settings()
    agent = Agent(
        OpenAIResponsesModel(
            settings.travel_model,
            provider=AlibabaProvider(
                api_key=settings.dashscope_api_key.get_secret_value(),
                base_url=settings.dashscope_base_url,
            ),
        ),
        name="知途 · Waywise",
        deps_type=TravelStore,
        output_type=[
            str,
            ToolOutput(present_arrangements, name="present_arrangements"),
        ],
        end_strategy="early",
        model_settings=OpenAIResponsesModelSettings(openai_reasoning_effort="medium"),
        instructions=Path(__file__)
        .with_name("instructions.md")
        .read_text(encoding="utf-8"),
        capabilities=[
            SummarizingCompaction(
                max_tokens=settings.compact_max_tokens,
                keep_messages=12,
                model_settings=OpenAIResponsesModelSettings(
                    openai_reasoning_effort="medium",
                ),
                event_stream_handler=drain_summary_events,
                instructions=(
                    "请把前面的旅行对话整理成一份摘要，让助手能接着帮用户规划。"
                    "记清楚用户想去哪、什么时候去、几个人、预算和偏好，以及已经订好的交通和酒店。"
                    "说明目前选了什么方案、用户是否确认、是否已经购买；同意方案不等于已经下单。"
                    "如果用户后来改了主意，以最新说法为准。还没解决的问题和查到的信息来源链接也要留下。"
                    "价格和余票等查询结果要保留查询时间，不能当作现在仍然有效。"
                    "对话里没说清楚的事就写明不确定，不要自行补全。"
                ),
            ),
            WebSearch(),
            MCP(
                "https://mcp.amap.com/mcp?"
                + urlencode(
                    {
                        "key": settings.amap_maps_api_key.get_secret_value(),
                    }
                ),
                tool_prefix="amap",
            ),
            LocalWorkspace(ROOT / "skills"),
            Skills(".", include=["flyai"]),
            FileSystem(read_only=True, tools=["read_file"]),
        ],
    )

    agent.tool(sequential=True)(present_products)

    @agent.tool_plain
    def call_flyai(args: list[str]) -> dict:
        """根据飞猪 Skill 执行旅行查询，返回退出码、原始标准输出和标准错误。

        先加载 flyai Skill 并阅读对应命令参考。args 填写子命令及各个参数，
        不包含 flyai 可执行文件名，例如 ["search-train", "--origin", "上海",
        "--destination", "杭州", "--dep-date", "2026-12-01"]。
        需要核对用法时传入 --help。查询失败或结果缺失时据实说明。
        """
        commands = {
            "keyword-search",
            "ai-search",
            "search-flight",
            "search-hotel",
            "search-train",
            "search-poi",
            "search-marriott-hotel",
            "search-marriott-package",
            "--help",
        }
        if not args or args[0] not in commands:
            raise ModelRetry(
                "请按飞猪 Skill 传入查询子命令及参数，或使用 --help 查看帮助。"
            )
        env = os.environ.copy()
        if key := settings.flyai_api_key.get_secret_value():
            env["FLYAI_API_KEY"] = key
        try:
            result = subprocess.run(
                ["flyai", *args],
                check=False,
                capture_output=True,
                text=True,
                timeout=60,
                env=env,
                cwd=ROOT / "skills",
            )
        except subprocess.TimeoutExpired:
            return {
                "returncode": None,
                "stdout": "",
                "stderr": "飞猪查询超过 60 秒，尚未取得结果。",
            }
        except FileNotFoundError:
            return {
                "returncode": None,
                "stdout": "",
                "stderr": "未找到 flyai CLI，请先安装 @fly-ai/flyai-cli。",
            }
        return {
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }

    @agent.tool_plain
    def current_time() -> str:
        """了解今天的北京时间。用户提到“下周”等相对日期、需要核对出行日期或注明查询时间时使用。

        返回日期、星期和时间，同一轮咨询可复用。
        """
        return f"当前北京时间：{datetime.now(ZoneInfo('Asia/Shanghai')):%Y-%m-%d %A %H:%M}。"

    @agent.tool
    async def confirm_arrangements(ctx: RunContext[TravelStore]) -> dict:
        """用户明确同意当前展示的方案后，确认并保存交通和住宿，再继续每日规划。

        自动读取当前会话的待确认方案，无需重新填写旅行数据。
        用户提出修改时先查询并用 present_arrangements 提交新方案，等待重新确认。
        """
        assert ctx.conversation_id is not None
        try:
            arrangements = await ctx.deps.arrangements.confirm(ctx.conversation_id)
        except ValueError as error:
            return {"success": False, "issues": [str(error)]}
        return {
            "success": True,
            "message": "交通和住宿已确认，可以开始每日行程规划。",
            "arrangements": arrangements.model_dump(mode="json"),
        }

    return agent
