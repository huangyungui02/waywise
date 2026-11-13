"""路由共用的应用依赖与会话读取。"""

from typing import Annotated, cast

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import Authentication
from app.chat.workflows import Replies
from app.db.conversations import ConversationStore
from app.db.tables import ConversationRow, UserRecord
from app.db.travel import TravelStore
from app.models.auth import TokenPayload
from app.settings import Settings


async def get_settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


def get_auth(request: Request) -> Authentication:
    return request.app.state.auth


async def get_access_payload(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(HTTPBearer())],
) -> TokenPayload:
    return get_auth(request).verify(credentials.credentials, "access")


async def get_current_user(
    request: Request,
    payload: TokenPayload = Depends(get_access_payload),
) -> UserRecord:
    async with AsyncSession((await get_store(request)).engine) as session:
        user, _ = await get_auth(request).identity(session, payload)
        return user


async def get_replies(request: Request) -> Replies:
    return cast(Replies, request.app.state.replies)


async def get_store(request: Request) -> TravelStore:
    return cast(TravelStore, request.app.state.store)


async def get_conversations(
    store: TravelStore = Depends(get_store),
) -> ConversationStore:
    return store.conversations


async def require_conversation(
    conversation_id: str,
    conversations: ConversationStore = Depends(get_conversations),
    user: UserRecord = Depends(get_current_user),
) -> ConversationRow:
    try:
        row = await conversations.get(conversation_id)
        if row.user_id != user.id:
            raise LookupError(conversation_id)
        return row
    except LookupError:
        raise HTTPException(404, "会话不存在") from None
