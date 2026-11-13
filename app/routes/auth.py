"""账号登录、刷新和会话撤销。"""

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.auth import Authentication, password_hash, token_hash, unauthorized
from app.db.tables import AuthSessionRecord, UserRecord
from app.db.travel import TravelStore
from app.dependencies import get_access_payload, get_auth, get_current_user, get_store
from app.models.auth import (
    ChangePassword,
    Login,
    Refresh,
    TokenPair,
    TokenPayload,
    UserInfo,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenPair)
async def login(
    body: Login,
    response: Response,
    auth: Authentication = Depends(get_auth),
    store: TravelStore = Depends(get_store),
):
    response.headers["Cache-Control"] = "no-store"
    async with AsyncSession(store.engine) as session, session.begin():
        return await auth.login(
            session, body.username, body.password.get_secret_value()
        )


@router.post("/refresh", response_model=TokenPair)
async def refresh(
    body: Refresh,
    response: Response,
    auth: Authentication = Depends(get_auth),
    store: TravelStore = Depends(get_store),
):
    response.headers["Cache-Control"] = "no-store"
    raw = body.refresh_token.get_secret_value()
    payload = auth.verify(raw, "refresh")
    async with AsyncSession(store.engine) as session, session.begin():
        user, login = await auth.identity(session, payload, lock=True)
        if login.refresh_token_hash != token_hash(raw):
            raise unauthorized()
        pair = auth.pair(user.id, login.id, login.expires_at)
        login.refresh_token_hash = token_hash(pair.refresh_token)
        return pair


@router.get("/me", response_model=UserInfo)
async def me(user: UserRecord = Depends(get_current_user)):
    return user


@router.post("/logout", status_code=204)
async def logout(
    payload: TokenPayload = Depends(get_access_payload),
    user: UserRecord = Depends(get_current_user),
    store: TravelStore = Depends(get_store),
):
    async with AsyncSession(store.engine) as session, session.begin():
        await session.execute(
            delete(AuthSessionRecord).where(
                AuthSessionRecord.id == payload.sid,
                AuthSessionRecord.user_id == user.id,
            )
        )


@router.post("/change-password", status_code=204)
async def change_password(
    body: ChangePassword,
    payload: TokenPayload = Depends(get_access_payload),
    auth: Authentication = Depends(get_auth),
    store: TravelStore = Depends(get_store),
):
    async with AsyncSession(store.engine) as session, session.begin():
        user, _ = await auth.identity(session, payload, lock=True)
        if not await run_in_threadpool(
            password_hash.verify,
            body.old_password.get_secret_value(),
            user.password_hash,
        ):
            raise HTTPException(400, "当前密码不正确")
        user.password_hash = await run_in_threadpool(
            password_hash.hash, body.new_password.get_secret_value()
        )
        await session.execute(
            delete(AuthSessionRecord).where(AuthSessionRecord.user_id == user.id)
        )
