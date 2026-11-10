"""会话、商品备选和交通住宿确认接口。"""

from dataclasses import asdict
from typing import Annotated

import anyio
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, StringConstraints
from pydantic_ai.ui.vercel_ai import VercelAIAdapter
from pydantic_ai_harness.step_persistence.conversations import ConversationSummary

from app.dependencies import RepliesDep, load_conversation
from app.models.arrangements import TravelArrangements
from app.settings import ROOT


router = APIRouter(prefix="/api/conversations")


class ConversationTitle(BaseModel):
    title: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
    ]


@router.get("")
async def list_conversations(replies: RepliesDep):
    return [asdict(item) for item in await replies.conversations.listing()]


@router.post("", status_code=201)
async def new_conversation(replies: RepliesDep):
    summary = await replies.conversations.save(
        summary=ConversationSummary(workspace=str(ROOT), title="新的旅行"),
        messages=[],
    )
    return asdict(summary)


@router.patch("/{conversation_id}", status_code=204)
async def rename_conversation(
    replies: RepliesDep, conversation_id: str, body: ConversationTitle
):
    saved = await load_conversation(conversation_id, replies)
    if not await replies.conversations.name(
        source=saved.summary, title=body.title, manual=True
    ):
        raise HTTPException(409, "会话已更新，请重新编辑标题")


@router.get("/{conversation_id}")
async def get_conversation(replies: RepliesDep, conversation_id: str):
    if reply := replies.running.get(conversation_id):
        await reply.ready.wait()
    saved = await load_conversation(conversation_id, replies)
    state = await anyio.to_thread.run_sync(
        replies.travel.arrangements.get_state, conversation_id
    )
    checkpoint = await replies.recovery(conversation_id)
    return {
        "products": await anyio.to_thread.run_sync(
            replies.travel.products.listing, conversation_id
        ),
        "recovery": checkpoint,
        "summary": asdict(saved.summary),
        "messages": [
            m.model_dump(mode="json", by_alias=True, exclude_none=True)
            for m in VercelAIAdapter.dump_messages(saved.messages, sdk_version=6)
        ],
        **{
            key: value.model_dump(mode="json")
            if isinstance(value, TravelArrangements)
            else value
            for key, value in state.items()
        },
    }


@router.delete("/{conversation_id}/products/{product_id}", status_code=204)
async def remove_product(replies: RepliesDep, conversation_id: str, product_id: str):
    await load_conversation(conversation_id, replies)
    if not await anyio.to_thread.run_sync(
        replies.travel.products.remove, conversation_id, product_id
    ):
        raise HTTPException(404, "备选商品不存在")


@router.post("/{conversation_id}/proposals/{proposal_id}/confirm")
async def confirm_proposal(replies: RepliesDep, conversation_id: str, proposal_id: str):
    await load_conversation(conversation_id, replies)
    if conversation_id in replies.busy:
        raise HTTPException(409, "请等待当前回复结束后确认")
    replies.busy.add(conversation_id)
    try:
        arrangements = await anyio.to_thread.run_sync(
            replies.travel.arrangements.confirm, conversation_id, proposal_id
        )
    except ValueError as error:
        raise HTTPException(409, str(error)) from None
    finally:
        replies.busy.discard(conversation_id)
    return arrangements.model_dump(mode="json")


@router.delete("/{conversation_id}", status_code=204)
async def delete_conversation(replies: RepliesDep, conversation_id: str):
    saved = await load_conversation(conversation_id, replies)
    if conversation_id in replies.busy:
        raise HTTPException(409, "请先停止当前回复，再删除会话")
    replies.busy.add(conversation_id)
    try:
        await replies.conversations.delete(source=saved.summary)
        await anyio.to_thread.run_sync(
            replies.travel.delete_conversation, conversation_id
        )
        await replies.redis.delete(replies.recovery_key(conversation_id))
    finally:
        replies.busy.discard(conversation_id)
