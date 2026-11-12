"""商品清单的持久化、去重与会话隔离。"""

import pytest
from pg_database import pg_database
from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel
from starlette.testclient import TestClient

from app.models.products import Product
from app.settings import Settings


@pytest.mark.anyio
async def test_products_update_and_reopen(tmp_path, store_factory):
    database = tmp_path / "travel.db"
    store = await store_factory(database)
    product = Product(
        name="酒店",
        description="近车站",
        price="¥100起/晚",
        purchase_url="https://example.com/hotel",
    )
    await store.products.save("first", [product, product])
    original = (await store.products.list("first"))[0]
    product.price = "¥120起/晚"
    await store.products.save("first", [product])
    updated = await store.products.list("first")
    assert len(updated) == 1
    assert updated[0].id == original.id
    assert updated[0].price == "¥120起/晚"
    assert updated[0].updated_at >= original.updated_at
    product.description = "12月5日—7日 标准间"
    await store.products.save("first", [product])
    await store.products.save("other", [product])
    reopened = await store_factory(database)
    assert len(await reopened.products.list("first")) == 1
    assert (await reopened.products.list("first"))[
        0
    ].description == "12月5日—7日 标准间"
    assert len(await reopened.products.list("other")) == 1
    assert not (await reopened.products.remove("other", original.id))
    assert await reopened.products.remove("first", original.id)
    assert (await reopened.products.list("first")) == []
    await reopened.products.delete_all("first")
    assert (await reopened.products.list("first")) == []
    assert len(await reopened.products.list("other")) == 1


@pytest.mark.anyio
async def test_product_endpoints(app_factory, tmp_path, store_factory):
    settings = Settings(
        _env_file=None,
        database_url=pg_database(tmp_path / "api.db"),
        DASHSCOPE_API_KEY="test-key",
        AMAP_MAPS_API_KEY="test-map",
        logfire_token="",
    )
    store = await store_factory(settings.database_url.get_secret_value())
    with TestClient(app_factory(settings, Agent(TestModel()))) as client:
        first = client.post("/api/conversations").json()["id"]
        other = client.post("/api/conversations").json()["id"]
        await store.products.save(
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
        await store.products.save(
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
        assert (await store.products.list(first)) == []
        assert client.delete(f"/api/conversations/{first}{path}").status_code == 404


@pytest.mark.anyio
async def test_concurrent_product_upserts_keep_one_stable_record(
    tmp_path, store_factory
):
    import asyncio

    store = await store_factory(tmp_path / "concurrent")
    product = Product(
        name="酒店", description="近车站", purchase_url="https://example.com/hotel"
    )
    await asyncio.gather(*(store.products.save("chat", [product]) for _ in range(8)))
    original = (await store.products.list("chat"))[0]
    product.price = "¥120起/晚"
    await asyncio.gather(*(store.products.save("chat", [product]) for _ in range(8)))
    records = await store.products.list("chat")
    assert len(records) == 1
    assert records[0].id == original.id
    assert records[0].price == product.price
    assert records[0].updated_at.utcoffset().total_seconds() == 0
