"""单 Agent，直接使用 PydanticAI 官方 Web UI 和集成。"""

from datetime import datetime
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from pydantic_ai import Agent, RunContext
from pydantic_ai.capabilities import MCP, Hooks, LocalWorkspace, WebSearch
from pydantic_ai.models.openai import OpenAIResponsesModel, OpenAIResponsesModelSettings
from pydantic_ai.providers.alibaba import AlibabaProvider
from pydantic_ai_harness import FileSystem, Shell, Skills

from settings import ROOT, Settings
from trip import Trip, TripStore


def create_agent(settings: Settings | None = None) -> Agent:
    settings = settings or Settings()
    hooks = Hooks()

    @hooks.on.run
    async def unlimited_requests(ctx: RunContext[TripStore], *, handler):
        # to_web() 未暴露 usage_limits，通过官方运行钩子取消默认的 50 次请求上限。
        ctx.usage_limits.request_limit = None
        return await handler()

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
        model_settings=OpenAIResponsesModelSettings(openai_reasoning_effort="none"),
        instructions=(ROOT / "instructions.md").read_text(encoding="utf-8"),
        capabilities=[
            hooks,
            WebSearch(),
            MCP("https://mcp.amap.com/mcp?" + urlencode({
                "key": settings.amap_maps_api_key.get_secret_value(),
            }), tool_prefix="amap"),
            LocalWorkspace(ROOT / "skills"),
            Skills(".", include=["flyai"]),
            FileSystem(read_only=True, tools=["read_file"]),
            Shell(
                allowed_commands=["flyai"],
                denied_operators=[";", "&&", "||", "|", ">", ">>", "<", "&", "`", "$(", "\n"],
                tools=["run_command"],
                default_timeout=60,
                env={"FLYAI_API_KEY": settings.flyai_api_key.get_secret_value()}
                if settings.flyai_api_key.get_secret_value() else None,
            ),
        ],
    )

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
        trip 填写已选定的直达往返交通与全部酒店，时间使用不带时区的北京时间。
        用户同意按方案规划不代表已经购买，购买状态按用户实际陈述填写。
        成功后继续规划每日行程；返回 issues 时与用户解决问题，重新确认后再提交。
        """
        issues = trip.issues()
        if issues:
            return {"success": False, "issues": issues}
        ctx.deps.confirmed[ctx.conversation_id] = trip
        return {"success": True, "message": "交通和住宿已保存，可以开始每日行程规划。",
                "trip": trip.model_dump(mode="json")}

    return agent


def create_app():
    return create_agent().to_web(deps=TripStore())
