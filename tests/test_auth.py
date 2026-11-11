"""个人 Bearer 令牌覆盖所有业务入口，健康检查与预检保持可用。"""

import pytest
from starlette.testclient import TestClient

from app.settings import Settings


@pytest.mark.parametrize("token", [None, ""])
def test_access_token_required(monkeypatch, token):
    if token is None:
        monkeypatch.delenv("ACCESS_TOKEN")
    else:
        monkeypatch.setenv("ACCESS_TOKEN", token)
    with pytest.raises(ValueError, match="access_token"):
        Settings(_env_file=None, DASHSCOPE_API_KEY="test", AMAP_MAPS_API_KEY="test")


def test_business_api_authentication(app_factory, tmp_path):
    backend = app_factory(
        Settings(
            _env_file=None,
            DASHSCOPE_API_KEY="test",
            AMAP_MAPS_API_KEY="test",
            database_path=tmp_path / "travel.db",
            cors_origins=["capacitor://localhost"],
        )
    )
    with TestClient(backend) as client:
        cid = client.post("/api/conversations").json()["id"]
        client.headers.clear()
        assert client.get("/api/health").status_code == 200
        assert client.get("/").status_code == 404
        assert client.get("/_app/missing.js").status_code == 404
        endpoints = [
            ("GET", "/api/conversations"),
            ("POST", "/api/conversations"),
            ("GET", f"/api/conversations/{cid}"),
            ("PATCH", f"/api/conversations/{cid}"),
            ("DELETE", f"/api/conversations/{cid}"),
            ("DELETE", f"/api/conversations/{cid}/products/missing"),
            ("POST", f"/api/conversations/{cid}/proposals/missing/confirm"),
            ("POST", f"/api/conversations/{cid}/chat"),
            ("POST", f"/api/conversations/{cid}/chat/stop"),
            ("GET", f"/api/conversations/{cid}/chat/stream"),
        ]
        for headers in [
            {},
            {"Authorization": "Bearer wrong"},
            {"Authorization": "Basic wrong"},
        ]:
            for method, path in endpoints:
                response = client.request(method, path, headers=headers)
                assert response.status_code == 401, (method, path, response.text)
                assert response.headers["www-authenticate"] == "Bearer"
        preflight = client.options(
            "/api/conversations",
            headers={
                "Origin": "capacitor://localhost",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "authorization,content-type",
            },
        )
        assert preflight.status_code == 200
        assert (
            "authorization" in preflight.headers["access-control-allow-headers"].lower()
        )
        client.headers["Authorization"] = "Bearer offline-access-token"
        assert client.get(f"/api/conversations/{cid}").status_code == 200
