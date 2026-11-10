"""Redis SDK 事件重放到官方 AI SDK 流响应的协议桥接。"""

from pydantic_ai.ui.vercel_ai import VercelAIAdapter
from pydantic_ai.ui.vercel_ai.response_types import (
    BaseChunk,
    DataChunk,
    DoneChunk,
    ErrorChunk,
)
from redis_fastapi import StreamBackend, StreamReader

from app.db.travel import TravelStore
from app.models.arrangements import TravelArrangements


class RecordedChunk(BaseChunk):
    encoded: str

    def encode(self, sdk_version: int) -> str:
        return self.encoded


async def stream_response(
    adapter: VercelAIAdapter[TravelStore, str | TravelArrangements],
    streams: StreamBackend,
    conversation_id: str,
    run_id: str,
    after: str = "0-0",
):
    reader = await streams.follow(run_id, scope=conversation_id, after=after)

    result = adapter.streaming_response(_stream_chunks(reader, run_id))
    result.headers.update({"Cache-Control": "no-store", "X-Accel-Buffering": "no"})
    return result


async def _stream_chunks(reader: StreamReader, run_id: str):
    async with reader:
        async for event in reader:
            if event.type == "ui":
                yield RecordedChunk(encoded=event.data)
            elif event.type in ("stream.error", "stream.gap"):
                yield ErrorChunk(error_text="连接中断，请重新同步最新进度")
            yield DataChunk(
                type="data-progress",
                data={"runId": run_id, "cursor": event.id},
                transient=True,
            )
        yield DoneChunk()
