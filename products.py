"""旅游商品备选；与聊天记录分开保存最新推荐。"""

from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, HttpUrl
from sqlalchemy import Text, UniqueConstraint, inspect
from sqlalchemy.engine import Engine
from sqlmodel import Field as SQLField, Session, SQLModel, col, select


class Product(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, str_min_length=1)

    name: str = Field(description="真实商品名称，不包含火车票或机票")
    description: str = Field(description="简短介绍或推荐理由，保留必要的平台提示")
    purchase_url: HttpUrl = Field(description="查询结果中的真实预订链接")
    image_url: HttpUrl | None = Field(
        default=None, description="查询返回的对应商品图片；没有可靠图片时留空"
    )
    price: str | None = Field(
        default=None,
        description="查询中的价格说明，保留起价、币种、按人或按房等单位及适用日期；未知时留空",
    )


class SavedProduct(Product):
    id: str
    updated_at: datetime


class ProductRecord(SQLModel, table=True):
    __tablename__ = "products"
    __table_args__ = (UniqueConstraint("conversation_id", "purchase_url"),)

    id: str = SQLField(primary_key=True, default_factory=lambda: str(uuid4()))
    conversation_id: str = SQLField(index=True)
    purchase_url: str
    data: str = SQLField(sa_type=Text)
    updated_at: datetime


class ProductStore:
    def __init__(self, engine: Engine):
        self.engine = engine
        # create_all 不修改已有表；旧版按 variant 分组的备选合并为每个链接的最新记录。
        if "variant" in {
            column["name"] for column in inspect(engine).get_columns("products")
        }:
            with engine.begin() as connection:
                connection.exec_driver_sql("BEGIN IMMEDIATE")
                records = (
                    connection.exec_driver_sql(
                        "SELECT id, conversation_id, purchase_url, data, updated_at "
                        "FROM products ORDER BY updated_at DESC, id"
                    )
                    .mappings()
                    .all()
                )
                connection.exec_driver_sql(
                    "ALTER TABLE products RENAME TO products_with_variant"
                )
                connection.exec_driver_sql(
                    "DROP INDEX IF EXISTS ix_products_conversation_id"
                )
                SQLModel.metadata.tables["products"].create(connection)
                seen: set[tuple[str, str]] = set()
                for record in records:
                    key = (record["conversation_id"], record["purchase_url"])
                    if key in seen:
                        continue
                    seen.add(key)
                    connection.exec_driver_sql(
                        "INSERT INTO products (id, conversation_id, purchase_url, data, updated_at) VALUES (?, ?, ?, ?, ?)",
                        (
                            record["id"],
                            *key,
                            Product.model_validate_json(
                                record["data"]
                            ).model_dump_json(),
                            record["updated_at"],
                        ),
                    )
                connection.exec_driver_sql("DROP TABLE products_with_variant")

    def save(self, conversation_id: str, products: list[Product]) -> None:
        with Session(self.engine) as session:
            for product in products:
                url = str(product.purchase_url)
                record = session.exec(
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
            records = session.exec(
                select(ProductRecord)
                .where(ProductRecord.conversation_id == conversation_id)
                .order_by(col(ProductRecord.updated_at).desc(), ProductRecord.id)
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
            for record in session.exec(
                select(ProductRecord).where(
                    ProductRecord.conversation_id == conversation_id
                )
            ):
                session.delete(record)
            session.commit()
