"""单 Agent，直接使用 PydanticAI 官方 Web UI 和集成。"""

from datetime import datetime
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from pydantic_ai import Agent
from pydantic_ai.capabilities import MCP, LocalWorkspace, WebSearch
from pydantic_ai.models.openai import OpenAIResponsesModel, OpenAIResponsesModelSettings
from pydantic_ai.providers.alibaba import AlibabaProvider
from pydantic_ai_harness import FileSystem, Shell, Skills

from settings import ROOT, Settings


def create_agent(settings: Settings | None = None) -> Agent:
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
        model_settings=OpenAIResponsesModelSettings(openai_reasoning_effort="none"),
        instructions=(ROOT / "instructions.md").read_text(encoding="utf-8"),
        capabilities=[
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

    @agent.instructions
    def current_time() -> str:
        return f"当前北京时间：{datetime.now(ZoneInfo('Asia/Shanghai')):%Y-%m-%d %A %H:%M}。"

    return agent


def create_app():
    return create_agent().to_web()
