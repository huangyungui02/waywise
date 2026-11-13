"""业务存储表；完整方案和商品由 Pydantic 模型校验并序列化为 JSON。"""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ArrangementsRecord(Base):
    """数据库记录；交通住宿安排仍由 TravelArrangements 校验并序列化为 JSON。"""

    __tablename__ = "arrangements"

    conversation_id: Mapped[str] = mapped_column(primary_key=True)
    data: Mapped[dict | None] = mapped_column(JSONB(none_as_null=True))
    pending_data: Mapped[dict | None] = mapped_column(JSONB(none_as_null=True))
    pending_id: Mapped[str | None]
    confirmed_id: Mapped[str | None]


class ProductRecord(Base):
    __tablename__ = "products"

    id: Mapped[str] = mapped_column(primary_key=True, default=lambda: str(uuid4()))
    conversation_id: Mapped[str]
    purchase_url: Mapped[str]
    data: Mapped[dict] = mapped_column(JSONB)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("conversation_id", "purchase_url"),
        Index("ix_products_recent", "conversation_id", updated_at.desc(), "id"),
    )


class ConversationRow(Base):
    __tablename__ = "conversation_records"

    id: Mapped[str] = mapped_column(primary_key=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), index=True)
    scope: Mapped[str | None]
    revision: Mapped[str]
    record_data: Mapped[dict] = mapped_column(JSONB)
    title: Mapped[str] = mapped_column(default="新的旅行")
    outcome: Mapped[str] = mapped_column(default="completed")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("ix_conversations_recent", updated_at.desc(), "id"),
        Index("ix_conversations_scope_recent", "scope", updated_at.desc(), "id"),
    )


class ConversationEntryRow(Base):
    __tablename__ = "conversation_entries"

    id: Mapped[str] = mapped_column(primary_key=True)
    parent_id: Mapped[str | None] = mapped_column(index=True)
    message_data: Mapped[dict] = mapped_column(JSONB)


class UserRecord(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(primary_key=True, default=lambda: str(uuid4()))
    username: Mapped[str] = mapped_column(unique=True)
    password_hash: Mapped[str]
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AuthSessionRecord(Base):
    __tablename__ = "auth_sessions"

    id: Mapped[str] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    refresh_token_hash: Mapped[str]
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
