"""业务存储表；完整方案和商品由 Pydantic 模型校验并序列化为 JSON。"""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ArrangementsRecord(Base):
    """数据库记录；交通住宿安排仍由 TravelArrangements 校验并序列化为 JSON。"""

    __tablename__ = "arrangements"

    conversation_id: Mapped[str] = mapped_column(primary_key=True)
    data: Mapped[str | None] = mapped_column(Text)
    pending_data: Mapped[str | None] = mapped_column(Text)
    pending_id: Mapped[str | None]
    confirmed_id: Mapped[str | None]


class ProductRecord(Base):
    __tablename__ = "products"
    __table_args__ = (UniqueConstraint("conversation_id", "purchase_url"),)

    id: Mapped[str] = mapped_column(primary_key=True, default=lambda: str(uuid4()))
    conversation_id: Mapped[str] = mapped_column(index=True)
    purchase_url: Mapped[str]
    data: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime]


class ConversationRow(Base):
    __tablename__ = "conversation_records"

    id: Mapped[str] = mapped_column(primary_key=True)
    scope: Mapped[str | None] = mapped_column(index=True)
    revision: Mapped[str]
    record_data: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(default="新的旅行")
    outcome: Mapped[str] = mapped_column(default="completed")
    updated_at: Mapped[datetime]


class ConversationEntryRow(Base):
    __tablename__ = "conversation_entries"

    id: Mapped[str] = mapped_column(primary_key=True)
    parent_id: Mapped[str | None] = mapped_column(index=True)
    message_data: Mapped[str] = mapped_column(Text)
