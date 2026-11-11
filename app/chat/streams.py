"""记录、读取 DBOS 原生事件流，并恢复中断时的模型消息。"""

from contextlib import aclosing
from uuid import uuid4

from dbos import DBOS, error
from pydantic import TypeAdapter
from pydantic_ai.messages import (
    ModelResponse,
    PartDeltaEvent,
    PartEndEvent,
    PartStartEvent,
    ThinkingPartDelta,
)

STREAM = "reply"
THINKING_DELTA = TypeAdapter(ThinkingPartDelta)


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
