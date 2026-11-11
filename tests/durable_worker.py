"""独立进程恢复测试：只有官方离线模型和本地工具，不访问网络。"""

import json
import sys
import time
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import anyio
from dbos import DBOS
from pydantic_ai import Agent
from pydantic_ai.durable_exec.dbos import DBOSDurability
from pydantic_ai.messages import ModelResponse, TextPart, ToolReturnPart
from pydantic_ai.models.function import DeltaToolCall, FunctionModel
from starlette.testclient import TestClient
from test_server import request

from app.chat.streams import record_events
from app.main import create_app
from app.settings import Settings

folder = Path(sys.argv[1])


async def model(messages, info):
    tool_done = any(isinstance(p, ToolReturnPart) for m in messages for p in m.parts)
    with (folder / "model-calls").open("a") as log:
        log.write("response\n" if tool_done else "tool\n")
    if not tool_done:
        yield {0: DeltaToolCall(name="query", json_args="{}", tool_call_id="query-1")}
        return
    if not (folder / "release").exists():
        yield "中断前的部分输出。"
        (folder / "started").touch()
        while not (folder / "release").exists():
            await anyio.sleep(0.02)
    yield "恢复后的完整答复。"


agent = Agent(
    FunctionModel(
        lambda messages, info: ModelResponse(parts=[TextPart("恢复测试")]),
        stream_function=model,
    ),
    name="recovery-test",
    capabilities=[
        DBOSDurability(
            event_stream_handler=record_events,
            model_step_config={"preemptible": True},
            parallel_execution_mode="sequential",
        )
    ],
)


@agent.tool_plain
@DBOS.step()
def query() -> str:
    """离线查询，记录实际执行次数。"""
    with (folder / "tool-calls").open("a") as log:
        log.write("query\n")
    return "工具已完成"


settings = Settings(
    _env_file=None,
    DASHSCOPE_API_KEY="test",
    AMAP_MAPS_API_KEY="test",
    database_path=folder / "travel.db",
    logfire_token="",
)
with (
    patch("app.main.Settings", return_value=settings),
    patch("app.main.create_agent", return_value=agent),
):
    backend = create_app()

with TestClient(backend) as client:
    if not (folder / "cid").exists():
        from pydantic_ai.ui.vercel_ai.request_types import SubmitMessage

        cid = client.post("/api/conversations").json()["id"]
        (folder / "cid").write_text(cid)
        client.portal.call(
            backend.state.replies.start,
            cid,
            SubmitMessage.model_validate(request("恢复旅行")),
        )
    else:
        cid = (folder / "cid").read_text()
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if (folder / "shutdown").exists():
            break
        detail = client.get(f"/api/conversations/{cid}").json()
        if detail["summary"]["outcome"] == "completed" and detail["messages"]:
            replay = client.get(f"/api/conversations/{cid}/chat/stream")
            (folder / "replay").write_text(replay.text)
            (folder / "done").write_text(json.dumps(detail, ensure_ascii=False))
            break
        time.sleep(0.05)
    else:
        raise RuntimeError("恢复测试超时")
