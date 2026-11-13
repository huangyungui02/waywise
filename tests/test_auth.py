"""真实 JWT、数据库登录会话、轮换与用户隔离。"""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from auth_helpers import TEST_PASSWORD, authenticate, ensure_user
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.testclient import TestClient

from app.auth import Authentication
from app.db.tables import AuthSessionRecord, UserRecord
from app.settings import Settings


@pytest.mark.parametrize("secret", [None, "", "short"])
def test_signing_key_required(monkeypatch, secret):
    if secret is None:
        monkeypatch.delenv("JWT_SECRET_KEY")
    else:
        monkeypatch.setenv("JWT_SECRET_KEY", secret)
    with pytest.raises(ValueError, match="jwt_secret_key"):
        Settings(_env_file=None, DASHSCOPE_API_KEY="test", AMAP_MAPS_API_KEY="test")


@pytest.fixture
def client(app_factory):
    backend = app_factory(
        Settings(
            _env_file=None,
            DASHSCOPE_API_KEY="test",
            AMAP_MAPS_API_KEY="test",
            cors_origins=["capacitor://localhost"],
        )
    )
    with TestClient(backend) as client:
        yield client


def bearer(token):
    return {"Authorization": "Bearer " + token}


def test_login_refresh_and_logout(client):
    tokens = authenticate(client)
    assert client.get("/api/auth/me").json()["username"] == "offline"
    refreshed = client.post(
        "/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert refreshed.status_code == 200, refreshed.text
    assert refreshed.headers["cache-control"] == "no-store"
    rotated = refreshed.json()
    assert rotated["refresh_token"] != tokens["refresh_token"]
    assert (
        client.post(
            "/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
        ).status_code
        == 401
    )
    assert (
        client.get("/api/auth/me", headers=bearer(rotated["refresh_token"])).status_code
        == 401
    )
    assert (
        client.post(
            "/api/auth/refresh", json={"refresh_token": rotated["access_token"]}
        ).status_code
        == 401
    )
    client.headers.update(bearer(rotated["access_token"]))
    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/auth/me").status_code == 401
    assert (
        client.post(
            "/api/auth/refresh", json={"refresh_token": rotated["refresh_token"]}
        ).status_code
        == 401
    )


def test_refresh_is_atomic(client):
    tokens = authenticate(client)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda _: (
                    client.post(
                        "/api/auth/refresh",
                        json={"refresh_token": tokens["refresh_token"]},
                    ).status_code
                ),
                range(2),
            )
        )
    assert sorted(results) == [200, 401]


def test_password_change_revokes_all_sessions(client):
    first = authenticate(client)
    second = authenticate(client)
    assert (
        client.post(
            "/api/auth/change-password",
            json={"old_password": "wrong", "new_password": "replacement-password"},
        ).status_code
        == 400
    )
    assert client.get("/api/auth/me").status_code == 200
    assert (
        client.post(
            "/api/auth/change-password",
            json={
                "old_password": TEST_PASSWORD,
                "new_password": "replacement-password",
            },
        ).status_code
        == 204
    )
    for tokens in [first, second]:
        assert (
            client.get(
                "/api/auth/me", headers=bearer(tokens["access_token"])
            ).status_code
            == 401
        )
        assert (
            client.post(
                "/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
            ).status_code
            == 401
        )
    assert (
        client.post(
            "/api/auth/login", json={"username": "offline", "password": TEST_PASSWORD}
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/auth/login",
            json={"username": "OFFLINE", "password": "replacement-password"},
        ).status_code
        == 200
    )


def test_user_isolation_and_unauthenticated_routes(client):
    owner = dict(client.headers)
    cid = client.post("/api/conversations").json()["id"]
    endpoints = [
        ("GET", f"/api/conversations/{cid}"),
        ("PATCH", f"/api/conversations/{cid}"),
        ("DELETE", f"/api/conversations/{cid}"),
        ("DELETE", f"/api/conversations/{cid}/products/missing"),
        ("POST", f"/api/conversations/{cid}/proposals/missing/confirm"),
        ("POST", f"/api/conversations/{cid}/chat"),
        ("POST", f"/api/conversations/{cid}/chat/stop"),
        ("GET", f"/api/conversations/{cid}/chat/stream"),
    ]
    authenticate(client, "other")
    assert client.get("/api/conversations").json() == []
    for method, path in endpoints:
        assert client.request(method, path).status_code == 404, path
    client.headers.clear()
    for headers in [
        {},
        {"Authorization": "Bearer wrong"},
        {"Authorization": "Basic wrong"},
    ]:
        for method, path in [
            ("GET", "/api/conversations"),
            ("POST", "/api/conversations"),
            *endpoints,
        ]:
            response = client.request(method, path, headers=headers)
            assert response.status_code == 401, (path, response.text)
            assert response.headers["www-authenticate"] == "Bearer"
    assert client.get("/api/health").status_code == 200
    assert (
        client.options(
            "/api/conversations",
            headers={
                "Origin": "capacitor://localhost",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "authorization,content-type",
            },
        ).status_code
        == 200
    )
    assert client.get(f"/api/conversations/{cid}", headers=owner).status_code == 200


def test_expiry_and_disabled_user(client):
    tokens = authenticate(client)
    payload = client.app.state.auth.verify(tokens["access_token"], "access")

    async def expire():
        async with (
            AsyncSession(client.app.state.store.engine) as session,
            session.begin(),
        ):
            row = await session.get(AuthSessionRecord, payload.sid)
            row.expires_at = datetime.now(UTC) - timedelta(seconds=1)

    client.portal.call(expire)
    assert client.get("/api/auth/me").status_code == 401
    assert (
        client.post(
            "/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
        ).status_code
        == 401
    )
    tokens = authenticate(client)

    async def disable():
        async with (
            AsyncSession(client.app.state.store.engine) as session,
            session.begin(),
        ):
            user = await session.scalar(
                select(UserRecord).where(UserRecord.username == "offline")
            )
            user.is_active = False

    client.portal.call(disable)
    assert client.get("/api/auth/me").status_code == 401
    assert (
        client.post(
            "/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/auth/login", json={"username": "offline", "password": TEST_PASSWORD}
        ).status_code
        == 401
    )


def test_invalid_credentials_and_expired_jwt(client):
    for username, password in [("missing", TEST_PASSWORD), ("offline", "wrong")]:
        assert (
            client.post(
                "/api/auth/login", json={"username": username, "password": password}
            ).status_code
            == 401
        )
    uid = client.portal.call(ensure_user, client.app.state.store)
    auth = client.app.state.auth
    expired = jwt.encode(
        {
            "sub": uid,
            "sid": "expired-session",
            "type": "access",
            "exp": datetime.now(UTC) - timedelta(seconds=1),
            "jti": "expired-token",
        },
        auth.secret,
        algorithm="HS256",
    )
    assert client.get("/api/auth/me", headers=bearer(expired)).status_code == 401
    tokens = authenticate(client)
    tampered = tokens["access_token"][:-8] + "invalid!"
    assert client.get("/api/auth/me", headers=bearer(tampered)).status_code == 401


@pytest.mark.parametrize(
    "change",
    [
        {"exp": None},
        {"sid": None},
        {"sid": 123},
        {"sub": ""},
        {"type": "refresh"},
        {"jti": ""},
    ],
)
def test_invalid_jwt_claims(change):
    auth = Authentication(
        Settings(_env_file=None, DASHSCOPE_API_KEY="test", AMAP_MAPS_API_KEY="test")
    )
    claims = {
        "sub": "user",
        "sid": "session",
        "type": "access",
        "exp": int((datetime.now(UTC) + timedelta(minutes=15)).timestamp()),
        "jti": "token",
        **change,
    }
    token = jwt.encode(claims, auth.secret, algorithm="HS256")
    with pytest.raises(HTTPException) as error:
        auth.verify(token, "access")
    assert error.value.status_code == 401


def test_jwt_rejects_other_algorithm():
    auth = Authentication(
        Settings(_env_file=None, DASHSCOPE_API_KEY="test", AMAP_MAPS_API_KEY="test")
    )
    token = jwt.encode(
        {
            "sub": "user",
            "sid": "session",
            "type": "access",
            "exp": int((datetime.now(UTC) + timedelta(minutes=15)).timestamp()),
            "jti": "token",
        },
        "offline-algorithm-test-signing-key-at-least-48-characters",
        algorithm="HS384",
    )
    with pytest.raises(HTTPException) as error:
        auth.verify(token, "access")
    assert error.value.status_code == 401


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("INITIAL_USERNAME", None),
        ("INITIAL_USERNAME", "invalid username"),
        ("INITIAL_PASSWORD", None),
        ("INITIAL_PASSWORD", "tiny!"),
    ],
)
def test_initial_credentials_validation(monkeypatch, field, value):
    if value is None:
        monkeypatch.delenv(field)
    else:
        monkeypatch.setenv(field, value)
    with pytest.raises(ValueError) as error:
        Settings(_env_file=None, DASHSCOPE_API_KEY="test", AMAP_MAPS_API_KEY="test")
    assert field.lower() in str(error.value)
    if field == "INITIAL_PASSWORD" and value:
        assert value not in str(error.value)


def test_initial_user_created_on_startup_and_password_preserved(app_factory):
    settings = Settings(
        _env_file=None,
        DASHSCOPE_API_KEY="test",
        AMAP_MAPS_API_KEY="test",
        initial_username="Initial.User",
        initial_password=TEST_PASSWORD,
    )
    credentials = {"username": "initial.user", "password": TEST_PASSWORD}
    with TestClient(app_factory(settings)) as client:
        response = client.post("/api/auth/login", json=credentials)
        assert response.status_code == 200
        client.headers.update(bearer(response.json()["access_token"]))
        original_id = client.get("/api/auth/me").json()["id"]
        assert (
            client.post(
                "/api/auth/change-password",
                json={
                    "old_password": TEST_PASSWORD,
                    "new_password": "changed-in-browser",
                },
            ).status_code
            == 204
        )
    with TestClient(app_factory(settings)) as client:
        assert client.post("/api/auth/login", json=credentials).status_code == 401
        response = client.post(
            "/api/auth/login",
            json={"username": "initial.user", "password": "changed-in-browser"},
        )
        assert response.status_code == 200
        client.headers.update(bearer(response.json()["access_token"]))
        assert client.get("/api/auth/me").json()["id"] == original_id
