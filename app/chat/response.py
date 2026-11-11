"""将 DBOS 持久事件转换为官方 Vercel AI HTTP 流响应。"""

from contextlib import aclosing
from dataclasses import dataclass

from dbos import DBOS
from pydantic_ai.exceptions import RunCancelled
from pydantic_ai.messages import CustomEvent
from pydantic_ai.ui.vercel_ai import VercelAIEventStream
from pydantic_ai.ui.vercel_ai.response_types import DataChunk

from .streams import STREAM, snapshot

RESYNC = "回复正在恢复，请重新同步"


@dataclass(kw_only=True)
class StreamProgress(CustomEvent):
    run_id: str
    cursor: int

    def to_payload(self):
        return DataChunk(
            type="data-progress",
            data={"runId": self.run_id, "cursor": str(self.cursor)},
            transient=True,
        )


async def stream_response(run_id):
    """原生事件由官方转换器还原；HTTP 断开只关闭订阅。"""

    async def events():
        execution_id = await DBOS.get_event_async(
            run_id, "execution", timeout_seconds=3600
        )
        records = await snapshot(execution_id) if execution_id else []
        latest = {step: attempt for step, attempt, _ in records}
        for offset, (step, attempt, event) in enumerate(records, 1):
            if not isinstance(event, list) and latest[step] == attempt:
                yield event
            yield StreamProgress(run_id=run_id, cursor=offset)
        offset = len(records)
        if execution_id:
            async with aclosing(
                DBOS.read_stream_async(execution_id, STREAM, offset=len(records))
            ) as reader:
                async for step, attempt, event in reader:
                    if step in latest and latest[step] != attempt:
                        raise RuntimeError(RESYNC)
                    latest[step] = attempt
                    offset += 1
                    if not isinstance(event, list):
                        yield event
                    yield StreamProgress(run_id=run_id, cursor=offset)
        handle = await DBOS.retrieve_workflow_async(run_id)
        try:
            outcome = await handle.get_result()
        except Exception:  # noqa: BLE001 — 对外隐藏工作流内部错误。
            raise RuntimeError("回复执行失败，请重试") from None
        if outcome == "cancelled":
            raise RunCancelled("回复已停止")

    encoder = VercelAIEventStream(sdk_version=6, server_message_id=run_id)

    response = encoder.streaming_response(encoder.transform_stream(events()))
    response.headers.update({"Cache-Control": "no-store", "X-Accel-Buffering": "no"})
    return response
