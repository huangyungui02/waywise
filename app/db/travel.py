"""旅行咨询的业务存储入口，会话、交通住宿与商品共用同一个 SQLite 文件。"""

from pathlib import Path

from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.db.arrangements import ArrangementStore
from app.db.conversations import ConversationStore
from app.db.products import ProductStore
from app.db.tables import Base


class TravelStore:
    def __init__(self, database: Path):
        # 三个 Store 共用异步 Engine，每个操作独立创建 Session。
        self.engine = create_async_engine(
            URL.create("sqlite+aiosqlite", database=str(database)), poolclass=NullPool
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
        await self.conversations.delete(conversation_id)
        await self.arrangements.delete(conversation_id)
        await self.products.delete_all(conversation_id)
