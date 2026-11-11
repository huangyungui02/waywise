"""DBOS 持久事件流与官方 Vercel AI 协议之间的桥接。"""

from contextlib import aclosing
from dataclasses import dataclass
from uuid import uuid4

from dbos import DBOS, error
from pydantic import TypeAdapter
from pydantic_ai.exceptions import RunCancelled
from pydantic_ai.messages import (
    CustomEvent,
    ModelResponse,
    PartDeltaEvent,
    PartEndEvent,
    PartStartEvent,
    ThinkingPartDelta,
)
from pydantic_ai.ui.vercel_ai import VercelAIEventStream
from pydantic_ai.ui.vercel_ai.response_types import DataChunk

STREAM = "reply"
RESYNC = "回复正在恢复，请重新同步"
THINKING_DELTA = TypeAdapter(ThinkingPartDelta)


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


async def record_events(ctx, events):
    """每个持久步骤的重试使用新片段，重连时丢弃同一步骤的旧片段。"""
    if DBOS.workflow_id is None:
        async for _ in events:
            pass
        return
    step = DBOS.step_id
    attempt = str(uuid4())
    await DBOS.write_stream_async(STREAM, (step, attempt, list(ctx.messages)))
    async for event in events:
        if isinstance(event, PartDeltaEvent) and isinstance(
            event.delta, ThinkingPartDelta
        ):
            # 官方 JSON 序列化会去掉临时合并回调；最终 Part 仍保留已解析的元数据。
            event = PartDeltaEvent(
                index=event.index,
                delta=THINKING_DELTA.validate_json(
                    THINKING_DELTA.dump_json(event.delta)
                ),
            )
        await DBOS.write_stream_async(STREAM, (step, attempt, event))


async def snapshot(run_id):
    records = []
    if await DBOS.get_workflow_status_async(run_id) is None:
        return records
    try:
        async with aclosing(
            DBOS.read_stream_async(run_id, STREAM, timeout_seconds=0)
        ) as reader:
            async for record in reader:
                records.append(record)
    except error.DBOSStreamTimeoutError:
        # 保留已读内容；超时仅表示暂时追平，并非流已结束。
        pass
    return records


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


def partial_messages(records, baseline):
    """用原生 part/delta 的 apply 恢复未完成响应，保留模型上下文。"""
    latest = {step: attempt for step, attempt, _ in records}
    messages = baseline
    parts = {}
    for step, attempt, event in records:
        if latest[step] != attempt:
            continue
        if isinstance(event, list):
            messages = event
            parts = {}
        elif isinstance(event, (PartStartEvent, PartEndEvent)):
            parts[event.index] = event.part
        elif isinstance(event, PartDeltaEvent) and event.index in parts:
            parts[event.index] = event.delta.apply(parts[event.index])
    if parts:
        messages = [
            *messages,
            ModelResponse(parts=[parts[index] for index in sorted(parts)]),
        ]
    return messages
