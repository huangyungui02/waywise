"""旅行商品备选的保存、查询和删除。"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.db.tables import ProductRecord
from app.models.products import Product, SavedProduct


class ProductStore:
    def __init__(self, engine: AsyncEngine):
        self.engine = engine

    async def save(self, conversation_id: str, products: list[Product]) -> None:
        async with AsyncSession(self.engine) as session:
            for product in products:
                url = str(product.purchase_url)
                statement = insert(ProductRecord).values(
                    conversation_id=conversation_id,
                    purchase_url=url,
                    data=product.model_dump(mode="json"),
                    updated_at=datetime.now(UTC),
                )
                await session.execute(
                    statement.on_conflict_do_update(
                        index_elements=[
                            ProductRecord.conversation_id,
                            ProductRecord.purchase_url,
                        ],
                        set_={
                            "data": statement.excluded.data,
                            "updated_at": statement.excluded.updated_at,
                        },
                    )
                )
            await session.commit()

    async def list(self, conversation_id: str) -> list[SavedProduct]:
        async with AsyncSession(self.engine) as session:
            records = (
                await session.scalars(
                    select(ProductRecord)
                    .where(ProductRecord.conversation_id == conversation_id)
                    .order_by(ProductRecord.updated_at.desc(), ProductRecord.id)
                )
            ).all()
            return [
                SavedProduct(
                    **Product.model_validate(record.data).model_dump(),
                    id=record.id,
                    updated_at=record.updated_at.astimezone(UTC),
                )
                for record in records
            ]

    async def remove(self, conversation_id: str, product_id: str) -> bool:
        async with AsyncSession(self.engine) as session:
            removed = await session.scalar(
                delete(ProductRecord)
                .where(
                    ProductRecord.id == product_id,
                    ProductRecord.conversation_id == conversation_id,
                )
                .returning(ProductRecord.id)
            )
            await session.commit()
            return removed is not None

    async def delete_all(self, conversation_id: str) -> None:
        async with AsyncSession(self.engine) as session:
            await session.execute(
                delete(ProductRecord).where(
                    ProductRecord.conversation_id == conversation_id
                )
            )
            await session.commit()
