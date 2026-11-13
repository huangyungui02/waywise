"""JWT 签发及数据库登录会话；退出、改密和停用即时生效。"""

from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Literal
from uuid import uuid4

import jwt
from fastapi import HTTPException
from pwdlib import PasswordHash
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.db.tables import AuthSessionRecord, UserRecord
from app.models.auth import TokenPair, TokenPayload
from app.settings import Settings

password_hash = PasswordHash.recommended()
# 不存在的账号也执行密码验证，避免明显的耗时差异。
_dummy_hash = password_hash.hash(str(uuid4()))


def unauthorized() -> HTTPException:
    return HTTPException(
        401, "登录已失效或凭据无效", headers={"WWW-Authenticate": "Bearer"}
    )


def token_hash(token: str) -> str:
    return sha256(token.encode()).hexdigest()


async def create_initial_user(
    session: AsyncSession, username: str, password: str
) -> None:
    if await session.scalar(
        select(UserRecord.id).where(UserRecord.username == username)
    ):
        return
    await session.execute(
        insert(UserRecord)
        .values(
            username=username,
            password_hash=await run_in_threadpool(password_hash.hash, password),
            created_at=datetime.now(UTC),
        )
        .on_conflict_do_nothing(index_elements=[UserRecord.username])
    )


class Authentication:
    def __init__(self, settings: Settings):
        self.secret = settings.jwt_secret_key.get_secret_value()

    def verify(self, token: str, kind: Literal["access", "refresh"]) -> TokenPayload:
        try:
            payload = TokenPayload.model_validate(
                jwt.decode(
                    token,
                    self.secret,
                    algorithms=["HS256"],
                    options={"require": ["sub", "sid", "type", "exp", "jti"]},
                )
            )
            if payload.type != kind:
                raise unauthorized()
            return payload
        except (jwt.InvalidTokenError, ValidationError):
            raise unauthorized() from None

    def pair(self, user_id: str, sid: str, expires_at: datetime) -> TokenPair:
        now = datetime.now(UTC)
        claims = {"sub": user_id, "sid": sid}
        return TokenPair(
            access_token=jwt.encode(
                {
                    **claims,
                    "type": "access",
                    "exp": min(now + timedelta(minutes=15), expires_at),
                    "jti": str(uuid4()),
                },
                self.secret,
                algorithm="HS256",
            ),
            refresh_token=jwt.encode(
                {**claims, "type": "refresh", "exp": expires_at, "jti": str(uuid4())},
                self.secret,
                algorithm="HS256",
            ),
        )

    async def login(
        self, session: AsyncSession, username: str, password: str
    ) -> TokenPair:
        user = await session.scalar(
            select(UserRecord).where(UserRecord.username == username)
        )
        valid = await run_in_threadpool(
            password_hash.verify, password, user.password_hash if user else _dummy_hash
        )
        if not valid or user is None or not user.is_active:
            raise unauthorized()
        # 与改密、刷新共用用户行锁，避免改密后在途登录重新建立旧凭据会话。
        await session.refresh(user, with_for_update=True)
        if not user.is_active or not await run_in_threadpool(
            password_hash.verify, password, user.password_hash
        ):
            raise unauthorized()
        now = datetime.now(UTC)
        sid = str(uuid4())
        expires_at = now + timedelta(days=30)
        pair = self.pair(user.id, sid, expires_at)
        session.add(
            AuthSessionRecord(
                id=sid,
                user_id=user.id,
                refresh_token_hash=token_hash(pair.refresh_token),
                expires_at=expires_at,
                created_at=now,
            )
        )
        return pair

    async def identity(
        self, session: AsyncSession, payload: TokenPayload, *, lock: bool = False
    ) -> tuple[UserRecord, AuthSessionRecord]:
        user_query = select(UserRecord).where(UserRecord.id == payload.sub)
        if lock:
            user_query = user_query.with_for_update()
        user = await session.scalar(user_query)
        query = select(AuthSessionRecord).where(
            AuthSessionRecord.id == payload.sid,
            AuthSessionRecord.user_id == payload.sub,
            AuthSessionRecord.expires_at > datetime.now(UTC),
        )
        if lock:
            query = query.with_for_update()
        login = await session.scalar(query)
        if user is None or not user.is_active or login is None:
            raise unauthorized()
        return user, login
