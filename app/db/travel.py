"""旅行咨询的业务存储入口，会话、交通住宿与商品共用 PostgreSQL 数据库。"""

from sqlalchemy import delete
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.db.arrangements import ArrangementStore
from app.db.conversations import ConversationStore
from app.db.products import ProductStore
from app.db.tables import ArrangementsRecord, Base, ConversationRow, ProductRecord


class TravelStore:
    def __init__(self, database: str):
        # 三个 Store 共用异步 Engine，每个操作独立创建 Session。
        url = make_url(database)
        if url.get_backend_name() != "postgresql":
            raise ValueError("DATABASE_URL 必须使用 PostgreSQL")
        self.engine = create_async_engine(
            url.set(drivername="postgresql+psycopg"),
            pool_pre_ping=True,
            hide_parameters=True,
        )
        self.conversations = ConversationStore(self.engine)
        self.arrangements = ArrangementStore(self.engine)
        self.products = ProductStore(self.engine)

    async def __aenter__(self):
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        return self

    async def __aexit__(self, *exc_info):
        await self.engine.dispose()

    async def delete_conversation(self, conversation_id: str) -> None:
        async with AsyncSession(self.engine) as session, session.begin():
            for table, column in (
                (ConversationRow, ConversationRow.id),
                (ArrangementsRecord, ArrangementsRecord.conversation_id),
                (ProductRecord, ProductRecord.conversation_id),
            ):
                await session.execute(delete(table).where(column == conversation_id))
