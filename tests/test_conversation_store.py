"""验证官方 ConversationStore 算法与 SQLAlchemy 原语的接线。"""

from datetime import UTC, datetime

import pytest
from pydantic_ai import Conversation
from pydantic_ai.conversation_store import ConversationConflict, ConversationRecord
from pydantic_ai.messages import ModelRequest, UserPromptPart
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.tables import ConversationEntryRow


def message(text):
    return ModelRequest(
        parts=[UserPromptPart(text, timestamp=datetime(2026, 12, 1, tzinfo=UTC))]
    )


@pytest.mark.anyio
async def test_append_window_branch_fork_and_delete_shared_history(
    tmp_path, store_factory
):
    store = await store_factory(tmp_path / "history.db")
    conversations = store.conversations

    conversation = Conversation(conversation_id="first", messages=[message("杭州")])
    entries = await conversations.save(conversation, scope="owner")
    assert len(entries) == 1
    assert await conversations.save(conversation) == []
    conversation.messages.append(message("两晚"))
    assert len(await conversations.save(conversation)) == 1
    loaded_entries = await conversations.load_entries("first")
    assert loaded_entries is not None and len(loaded_entries) == 2
    window = await conversations.load("first", limit=1)
    assert window is not None
    assert window.messages == [message("两晚")]
    window.messages.append(message("近车站"))
    await conversations.save(window)
    assert len((await conversations.load("first")).messages) == 3
    assert await conversations.load("first", scope="other") is None
    assert await conversations.list_conversations(scope="other") == []
    assert len(await conversations.list_conversations(scope="owner")) == 1

    fork = await conversations.fork(
        "first", at=1, new_conversation_id="fork", scope="owner"
    )
    fork_entries = await conversations.load_entries("fork")
    assert fork_entries is not None and fork_entries[0].id == entries[0].id
    fork.messages.append(message("改成一天"))
    await conversations.save(fork)
    first = await conversations.load("first")
    assert first is not None
    branch = await conversations.branch("first", at=1, expected_revision=first.revision)
    branch.messages.append(message("改住湖边"))
    await conversations.save(branch)
    reopened = (await store_factory(tmp_path / "history.db")).conversations
    assert (await reopened.load("first")).messages == [
        message("杭州"),
        message("改住湖边"),
    ]
    record = await reopened.read_record("first")
    assert record is not None and record.branches

    await conversations.delete("first", scope="other")
    assert await conversations.load("first") is not None
    await conversations.delete("first")
    assert await conversations.load("first") is None
    assert (await reopened.load("fork")).messages == [
        message("杭州"),
        message("改成一天"),
    ]
    # 官方允许后端保留消息日志；删除不能破坏其他会话共享的历史。
    await conversations.delete("fork")
    assert await conversations.load("fork") is None


@pytest.mark.anyio
async def test_stale_write_and_missing_fork_head_roll_back(tmp_path, store_factory):
    store = await store_factory(tmp_path / "conflicts.db")
    conversations = store.conversations

    conversation = Conversation(conversation_id="first", messages=[message("杭州")])
    await conversations.save(conversation)
    stale = await conversations.load("first")
    current = await conversations.load("first")
    assert stale is not None and current is not None
    current.messages.append(message("两人"))
    await conversations.save(current)
    stale.messages.append(message("三人"))
    with pytest.raises(ConversationConflict):
        await conversations.save(stale)
    with pytest.raises(ConversationConflict):
        await conversations.save(
            Conversation(conversation_id="first", messages=[message("覆盖")])
        )
    missing = ConversationRecord(conversation_id="missing", head_id="deleted-entry")
    with pytest.raises(ConversationConflict):
        await conversations.write_record(missing, expected_revision=None)
    assert await conversations.load("missing") is None
    assert (await conversations.load("first")).messages == current.messages
    async with AsyncSession(store.engine) as session:
        assert (
            await session.scalar(select(func.count()).select_from(ConversationEntryRow))
        ) == 2


@pytest.mark.anyio
async def test_rename_and_recover_status_without_rewriting_history(
    tmp_path, store_factory
):
    conversations = (await store_factory(tmp_path / "titles.db")).conversations
    created = await conversations.create()
    conversation = await conversations.load(created.id)
    await conversations.rename(created.id, "自己起的名字")
    await conversations.save_messages(conversation, [message("杭州")], "running")
    record = await conversations.read_record(created.id)
    await conversations.recover_interrupted_runs()
    recovered = await conversations.load(created.id)
    metadata = await conversations.get(created.id)
    assert metadata.title == "自己起的名字"
    assert metadata.outcome == "cancelled"
    assert recovered.messages == [message("杭州")]
    assert await conversations.read_record(created.id) == record


@pytest.mark.anyio
async def test_inflight_load_can_finish_from_retained_log_after_delete(
    tmp_path, monkeypatch, store_factory
):
    conversations = (await store_factory(tmp_path / "delete-race.db")).conversations

    await conversations.save(
        Conversation(conversation_id="first", messages=[message("杭州")])
    )
    read_history = conversations.read_history

    async def delete_before_history(head_id, *, limit=None):
        await conversations.delete("first")
        return await read_history(head_id, limit=limit)

    monkeypatch.setattr(conversations, "read_history", delete_before_history)
    # 读取已取得记录时可以完成该次快照；之后的读取必须看不到已删除会话。
    loaded = await conversations.load("first")
    assert loaded is not None and loaded.messages == [message("杭州")]
    assert await conversations.load("first") is None
