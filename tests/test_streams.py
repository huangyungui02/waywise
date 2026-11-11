"""持久流中的临时思考增量应遵循 PydanticAI 的序列化约定。"""

import pickle
from types import SimpleNamespace

import anyio
import pytest
from pydantic_ai.messages import (
    PartDeltaEvent,
    PartEndEvent,
    PartStartEvent,
    ThinkingPart,
    ThinkingPartDelta,
)

from app import streams


@pytest.mark.parametrize("callback", [False, True])
def test_thinking_delta_persistence(monkeypatch, callback):
    records = []
    details = {"raw_content": "思考"}

    def update_provider_details(existing):
        return {**(existing or {}), **details}

    delta = ThinkingPartDelta(
        content_delta="思考",
        provider_name="alibaba",
        provider_details=update_provider_details if callback else details,
    )
    original = PartDeltaEvent(index=0, delta=delta)
    initial = ThinkingPart(content="", provider_name="alibaba")
    final = delta.apply(initial)

    async def write_stream(name, record):
        # 复现 DBOS 默认持久化边界，而非仅检查事件可以转 JSON。
        records.append(pickle.loads(pickle.dumps(record)))

    monkeypatch.setattr(
        streams,
        "DBOS",
        SimpleNamespace(workflow_id="run", step_id=1, write_stream_async=write_stream),
    )

    async def events():
        yield PartStartEvent(index=0, part=initial)
        yield original
        yield PartEndEvent(index=0, part=final)

    anyio.run(streams.record_events, SimpleNamespace(messages=[]), events())
    stored_delta = records[2][2].delta
    assert stored_delta.content_delta == "思考"
    assert stored_delta.provider_details == (None if callback else details)
    assert original.delta is delta
    assert delta.provider_details is (update_provider_details if callback else details)
    # 停止于增量时仍可恢复文本，结束事件恢复完整 provider 元数据。
    partial = streams.partial_messages(records[:-1], [])
    assert partial[-1].parts[0].content == "思考"
    completed = streams.partial_messages(records, [])
    assert completed[-1].parts[0].provider_details == details
