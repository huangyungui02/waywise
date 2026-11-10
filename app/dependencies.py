"""路由共用的应用依赖与会话读取。"""

from typing import Annotated, cast

from fastapi import Depends, HTTPException, Request
from pydantic_ai_harness.step_persistence.conversations import SavedConversation

from app.replies import Replies


def get_replies(request: Request) -> Replies:
    return cast(Replies, request.app.state.replies)


RepliesDep = Annotated[Replies, Depends(get_replies)]


async def load_conversation(
    conversation_id: str, replies: Replies
) -> SavedConversation:
    try:
        return await replies.conversations.get(conversation_id=conversation_id)
    except LookupError:
        raise HTTPException(404, "会话不存在") from None
