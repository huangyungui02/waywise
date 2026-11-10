"""商品清单的持久化、去重与会话隔离。"""

from starlette.testclient import TestClient
from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel

from app.models.products import Product
from app.settings import Settings
from app.db.travel import TravelStore


def test_products_update_and_reopen(tmp_path):
    database = tmp_path / "travel.db"
    store = TravelStore(database)
    product = Product(
        name="酒店",
        description="近车站",
        price="¥100起/晚",
        purchase_url="https://example.com/hotel",
    )
    store.products.save("first", [product, product])
    original = store.products.listing("first")[0]
    product.price = "¥120起/晚"
    store.products.save("first", [product])
    updated = store.products.listing("first")
    assert len(updated) == 1
    assert updated[0].id == original.id
    assert updated[0].price == "¥120起/晚"
    assert updated[0].updated_at >= original.updated_at
    product.description = "12月5日—7日 标准间"
    store.products.save("first", [product])
    store.products.save("other", [product])
    reopened = TravelStore(database)
    assert len(reopened.products.listing("first")) == 1
    assert reopened.products.listing("first")[0].description == "12月5日—7日 标准间"
    assert len(reopened.products.listing("other")) == 1
    assert not reopened.products.remove("other", original.id)
    assert reopened.products.remove("first", original.id)
    assert reopened.products.listing("first") == []
    reopened.delete_conversation("first")
    assert reopened.products.listing("first") == []
    assert len(reopened.products.listing("other")) == 1


def test_product_endpoints(app_factory, tmp_path):
    settings = Settings(
        _env_file=None,
        database_path=tmp_path / "api.db",
        DASHSCOPE_API_KEY="test-key",
        AMAP_MAPS_API_KEY="test-map",
        logfire_token="",
    )
    store = TravelStore(settings.database_path)
    with TestClient(app_factory(settings, Agent(TestModel()))) as client:
        first = client.post("/api/conversations").json()["id"]
        other = client.post("/api/conversations").json()["id"]
        store.products.save(
            first,
            [
                Product(
                    name="门票",
                    description="成人票",
                    purchase_url="https://example.com/ticket",
                )
            ],
        )
        product = client.get(f"/api/conversations/{first}").json()["products"][0]
        assert product["updated_at"]
        assert client.get(f"/api/conversations/{other}").json()["products"] == []
        path = f"/products/{product['id']}"
        assert client.delete(f"/api/conversations/{other}{path}").status_code == 404
        assert client.delete(f"/api/conversations/{first}{path}").status_code == 204
        assert client.get(f"/api/conversations/{first}").json()["products"] == []
        store.products.save(
            first,
            [
                Product(
                    name="门票",
                    description="成人票",
                    purchase_url="https://example.com/ticket",
                )
            ],
        )
        assert client.delete(f"/api/conversations/{first}").status_code == 204
        assert store.products.listing(first) == []
        assert client.delete(f"/api/conversations/{first}{path}").status_code == 404
