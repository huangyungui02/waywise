"""旅行商品备选的保存、查询和删除。"""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from models.products import Product, SavedProduct
from storage.models import ProductRecord


class ProductStore:
    def __init__(self, engine: Engine):
        self.engine = engine

    def save(self, conversation_id: str, products: list[Product]) -> None:
        with Session(self.engine) as session:
            for product in products:
                url = str(product.purchase_url)
                record = session.scalars(
                    select(ProductRecord).where(
                        ProductRecord.conversation_id == conversation_id,
                        ProductRecord.purchase_url == url,
                    )
                ).first()
                if record is None:
                    record = ProductRecord(
                        conversation_id=conversation_id,
                        purchase_url=url,
                        data=product.model_dump_json(),
                        updated_at=datetime.now(timezone.utc),
                    )
                else:
                    record.data = product.model_dump_json()
                    record.updated_at = datetime.now(timezone.utc)
                session.add(record)
                session.flush()
            session.commit()

    def listing(self, conversation_id: str) -> list[SavedProduct]:
        with Session(self.engine) as session:
            records = session.scalars(
                select(ProductRecord)
                .where(ProductRecord.conversation_id == conversation_id)
                .order_by(ProductRecord.updated_at.desc(), ProductRecord.id)
            ).all()
            return [
                SavedProduct(
                    **Product.model_validate_json(record.data).model_dump(),
                    id=record.id,
                    updated_at=record.updated_at.replace(tzinfo=timezone.utc),
                )
                for record in records
            ]

    def remove(self, conversation_id: str, product_id: str) -> bool:
        with Session(self.engine) as session:
            record = session.get(ProductRecord, product_id)
            if record is None or record.conversation_id != conversation_id:
                return False
            session.delete(record)
            session.commit()
            return True

    def delete_all(self, conversation_id: str) -> None:
        with Session(self.engine) as session:
            for record in session.scalars(
                select(ProductRecord).where(
                    ProductRecord.conversation_id == conversation_id
                )
            ):
                session.delete(record)
            session.commit()
