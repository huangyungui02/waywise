"""旅行咨询的业务存储入口，共用同一个 SQLite Engine。"""

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.pool import NullPool

from storage.arrangements import ArrangementsStore
from storage.models import Base
from storage.products import ProductStore


class TravelStore:
    def __init__(self, database: Path):
        # 与官方会话 Store 共用文件，每个 Session 结束后关闭连接。
        self.engine = create_engine(
            URL.create("sqlite", database=str(database)), poolclass=NullPool
        )
        Base.metadata.create_all(self.engine)
        self.arrangements = ArrangementsStore(self.engine)
        self.products = ProductStore(self.engine)

    def delete_conversation(self, conversation_id: str) -> None:
        self.arrangements.delete(conversation_id)
        self.products.delete_all(conversation_id)
