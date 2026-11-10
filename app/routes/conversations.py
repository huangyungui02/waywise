"""会话、商品备选和交通住宿确认接口。"""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import AfterValidator, BaseModel, ConfigDict, StringConstraints
from pydantic_ai.ui.vercel_ai import VercelAIAdapter

from app.db.conversations import ConversationStore
from app.db.tables import ConversationRow
from app.db.travel import TravelStore
from app.dependencies import (
    get_conversations,
    get_replies,
    get_store,
    require_conversation,
)
from app.models.arrangements import TravelArrangements
from app.replies import Replies

router = APIRouter(prefix="/api/conversations")


class ConversationSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    outcome: str
    updated_at: Annotated[
        datetime, AfterValidator(lambda value: value.replace(tzinfo=UTC))
    ]


class ConversationTitle(BaseModel):
    title: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
    ]


@router.get("", response_model=list[ConversationSummary])
async def list_conversations(
    conversations: ConversationStore = Depends(get_conversations),
):
    return await conversations.list()


@router.post("", status_code=201, response_model=ConversationSummary)
async def new_conversation(
    conversations: ConversationStore = Depends(get_conversations),
):
    return await conversations.create()


@router.patch(
    "/{conversation_id}", status_code=204, dependencies=[Depends(require_conversation)]
)
async def rename_conversation(
    conversation_id: str,
    body: ConversationTitle,
    conversations: ConversationStore = Depends(get_conversations),
):
    await conversations.rename(conversation_id, body.title)


@router.get("/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    record: ConversationRow = Depends(require_conversation),
    replies: Replies = Depends(get_replies),
    conversations: ConversationStore = Depends(get_conversations),
    store: TravelStore = Depends(get_store),
):
    if reply := replies.running.get(conversation_id):
        await reply.ready.wait()
        record = await conversations.get(conversation_id)
    conversation = await conversations.load(conversation_id)
    if conversation is None:
        raise HTTPException(404, "会话不存在")
    state = await store.arrangements.get_state(conversation_id)
    checkpoint = await replies.recovery(conversation_id)
    return {
        "products": await store.products.list(conversation_id),
        "recovery": checkpoint,
        "summary": ConversationSummary.model_validate(record),
        "messages": [
            m.model_dump(mode="json", by_alias=True, exclude_none=True)
            for m in VercelAIAdapter.dump_messages(conversation.messages, sdk_version=6)
        ],
        **{
            key: value.model_dump(mode="json")
            if isinstance(value, TravelArrangements)
            else value
            for key, value in state.items()
        },
    }


@router.delete(
    "/{conversation_id}/products/{product_id}",
    status_code=204,
    dependencies=[Depends(require_conversation)],
)
async def remove_product(
    conversation_id: str,
    product_id: str,
    store: TravelStore = Depends(get_store),
):
    if not await store.products.remove(conversation_id, product_id):
        raise HTTPException(404, "备选商品不存在")


@router.post(
    "/{conversation_id}/proposals/{proposal_id}/confirm",
    dependencies=[Depends(require_conversation)],
)
async def confirm_proposal(
    conversation_id: str,
    proposal_id: str,
    replies: Replies = Depends(get_replies),
    store: TravelStore = Depends(get_store),
):
    if conversation_id in replies.busy:
        raise HTTPException(409, "请等待当前回复结束后确认")
    replies.busy.add(conversation_id)
    try:
        arrangements = await store.arrangements.confirm(conversation_id, proposal_id)
    except ValueError as error:
        raise HTTPException(409, str(error)) from None
    finally:
        replies.busy.discard(conversation_id)
    return arrangements.model_dump(mode="json")


@router.delete(
    "/{conversation_id}", status_code=204, dependencies=[Depends(require_conversation)]
)
async def delete_conversation(
    conversation_id: str,
    replies: Replies = Depends(get_replies),
    store: TravelStore = Depends(get_store),
):
    if conversation_id in replies.busy:
        raise HTTPException(409, "请先停止当前回复，再删除会话")
    replies.busy.add(conversation_id)
    try:
        await store.delete_conversation(conversation_id)
        await replies.clear_recovery(conversation_id)
    finally:
        replies.busy.discard(conversation_id)
