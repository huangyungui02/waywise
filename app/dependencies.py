"""路由共用的应用依赖与会话读取。"""

from secrets import compare_digest
from typing import Annotated, cast

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.chat.workflows import Replies
from app.db.conversations import ConversationStore
from app.db.tables import ConversationRow
from app.db.travel import TravelStore
from app.settings import Settings


async def get_settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


async def require_access_token(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(HTTPBearer())],
    settings: Annotated[Settings, Depends(get_settings)],
):
    if not compare_digest(
        credentials.credentials.encode(),
        settings.access_token.get_secret_value().encode(),
    ):
        raise HTTPException(401, "访问令牌无效", headers={"WWW-Authenticate": "Bearer"})


async def get_replies(request: Request) -> Replies:
    return cast(Replies, request.app.state.replies)


async def get_store(request: Request) -> TravelStore:
    return cast(TravelStore, request.app.state.store)


async def get_conversations(
    store: TravelStore = Depends(get_store),
) -> ConversationStore:
    return store.conversations


async def require_conversation(
    conversation_id: str, conversations: ConversationStore = Depends(get_conversations)
) -> ConversationRow:
    try:
        return await conversations.get(conversation_id)
    except LookupError:
        raise HTTPException(404, "会话不存在") from None
