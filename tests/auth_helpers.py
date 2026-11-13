"""离线测试账号；测试通过真实登录接口获取令牌。"""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import password_hash
from app.db.tables import UserRecord

TEST_PASSWORD = "offline-test-password"


async def ensure_user(store, username="offline"):
    async with AsyncSession(store.engine) as session, session.begin():
        user = await session.scalar(
            select(UserRecord).where(UserRecord.username == username)
        )
        if user is None:
            user = UserRecord(
                username=username,
                password_hash=password_hash.hash(TEST_PASSWORD),
                created_at=datetime.now(UTC),
            )
            session.add(user)
            await session.flush()
        return user.id


def authenticate(client, username="offline"):
    client.portal.call(ensure_user, client.app.state.store, username)
    response = client.post(
        "/api/auth/login", json={"username": username, "password": TEST_PASSWORD}
    )
    assert response.status_code == 200, response.text
    tokens = response.json()
    client.headers["Authorization"] = "Bearer " + tokens["access_token"]
    return tokens
