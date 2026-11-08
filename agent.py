"""旅行 Agent：使用 PydanticAI 官方工具集成。"""

import os
import subprocess
from datetime import datetime
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from pydantic_ai import Agent, ModelRetry, RunContext, ToolOutput
from pydantic_ai.capabilities import MCP, LocalWorkspace, WebSearch
from pydantic_ai.models.openai import OpenAIResponsesModel, OpenAIResponsesModelSettings
from pydantic_ai.providers.alibaba import AlibabaProvider
from pydantic_ai_harness import FileSystem, Skills

from settings import ROOT, Settings
from trip import Trip, TripStore


def present_trip(ctx: RunContext[TripStore], trip: Trip) -> Trip:
    """提交选定的完整往返交通和住宿，以卡片展示并结束本轮，等待用户确认。

    提交前核实往返方向、酒店位置和全部日期，未购买的商品必须有真实预订链接。
    预计抵达时间需有依据并提前向用户说明；购买状态以用户陈述为准。
    校验失败时修正方案后重新提交，成功后等待用户确认或提出修改。
    """
    if issues := trip.issues():
        raise ModelRetry("；".join(issues))
    assert ctx.conversation_id is not None and ctx.tool_call_id is not None
    ctx.deps.present(ctx.conversation_id, trip, ctx.tool_call_id)
    return trip


def create_agent(settings: Settings | None = None) -> Agent[TripStore, str | Trip]:
    settings = settings or Settings()
    agent = Agent(
        OpenAIResponsesModel(
            settings.travel_model,
            provider=AlibabaProvider(
                api_key=settings.dashscope_api_key.get_secret_value(),
                base_url=settings.dashscope_base_url,
            ),
        ),
        name="国内旅行助手",
        deps_type=TripStore,
        output_type=[str, ToolOutput(present_trip, name="present_trip")],
        end_strategy="early",
        model_settings=OpenAIResponsesModelSettings(openai_reasoning_effort="medium"),
        instructions=(ROOT / "instructions.md").read_text(encoding="utf-8"),
        capabilities=[
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
    def confirm_trip(ctx: RunContext[TripStore]) -> dict:
        """用户明确同意当前展示的方案后，确认并保存交通和住宿，再继续每日规划。

        自动读取当前会话的待确认方案，无需重新填写旅行数据。
        用户提出修改时先查询并用 present_trip 提交新方案，等待重新确认。
        """
        assert ctx.conversation_id is not None
        try:
            trip = ctx.deps.confirm(ctx.conversation_id)
        except ValueError as error:
            return {"success": False, "issues": [str(error)]}
        return {
            "success": True,
            "message": "交通和住宿已确认，可以开始每日行程规划。",
            "trip": trip.model_dump(mode="json"),
        }

    return agent
