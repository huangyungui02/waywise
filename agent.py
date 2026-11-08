"""旅行 Agent：使用 PydanticAI 官方工具集成。"""

import os
import subprocess
from datetime import datetime
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from pydantic_ai import Agent, ModelRetry, RunContext
from pydantic_ai.capabilities import MCP, LocalWorkspace, WebSearch
from pydantic_ai.models.openai import OpenAIResponsesModel, OpenAIResponsesModelSettings
from pydantic_ai.providers.alibaba import AlibabaProvider
from pydantic_ai_harness import FileSystem, Skills

from settings import ROOT, Settings
from trip import Trip, TripStore


def create_agent(settings: Settings | None = None) -> Agent[TripStore, str]:
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
    def confirm_trip(ctx: RunContext[TripStore], trip: Trip) -> dict:
        """保存用户选定的往返交通和住宿，作为接下来安排每日游览的依据。

        先了解需求、补齐未订的交通和酒店，将完整方案展示给用户；用户明确同意后再调用。
        trip 填写整体出发地、目的地、已选定的直达往返交通与全部酒店。
        提交前核实往返方向与酒店位置，交通填写具体上下车地点。
        时间使用不带时区的北京时间，采用有依据的预计抵达时间时，先向用户说明。
        用户同意按方案规划不代表已经购买，购买状态按用户实际陈述填写。
        成功后继续规划每日行程；返回 issues 时与用户解决问题，重新确认后再提交。
        """
        issues = trip.issues()
        if issues:
            return {"success": False, "issues": issues}
        assert ctx.conversation_id is not None  # Agent 在运行开始时解析会话 ID。
        ctx.deps.save(ctx.conversation_id, trip)
        return {
            "success": True,
            "message": "交通和住宿已保存，可以开始每日行程规划。",
            "trip": trip.model_dump(mode="json"),
        }

    return agent
