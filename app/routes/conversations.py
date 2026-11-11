"""会话、商品备选和交通住宿确认接口。"""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import AfterValidator, BaseModel, ConfigDict, StringConstraints

from app.chat.workflows import Replies
from app.db.conversations import ConversationStore
from app.db.tables import ConversationRow
from app.db.travel import TravelStore
from app.dependencies import (
    get_conversations,
    get_replies,
    get_store,
    require_access_token,
    require_conversation,
)
from app.models.arrangements import TravelArrangements

router = APIRouter(
    prefix="/api/conversations", dependencies=[Depends(require_access_token)]
)


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
    replies: Replies = Depends(get_replies),
):
    records = await conversations.list()
    for record in records:
        record.outcome = await replies.outcome(record.id, record.outcome)
    return records


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
    conversation = await conversations.load(conversation_id)
    if conversation is None:
        raise HTTPException(404, "会话不存在")
    state = await store.arrangements.get_state(conversation_id)
    checkpoint = await replies.recovery(conversation_id)
    record.outcome = await replies.outcome(conversation_id, record.outcome)
    return {
        "products": await store.products.list(conversation_id),
        "recovery": checkpoint,
        "summary": ConversationSummary.model_validate(record),
        "messages": replies.ui_messages(conversation.messages),
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
):
    handle = await replies.submit(conversation_id, "confirm", proposal_id)
    result = await handle.get_result()
    if "error" in result:
        raise HTTPException(409, result["error"])
    return result


@router.delete(
    "/{conversation_id}", status_code=204, dependencies=[Depends(require_conversation)]
)
async def delete_conversation(
    conversation_id: str,
    replies: Replies = Depends(get_replies),
):
    handle = await replies.submit(conversation_id, "delete", "")
    await handle.get_result()
