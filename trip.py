"""直达、单目的地旅行的基础安排；只保存用户明确确认的方案。"""

from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, HttpUrl, NaiveDatetime
from sqlalchemy import Text
from sqlalchemy.engine import URL, Engine
from sqlalchemy.pool import NullPool
from sqlmodel import Field, Session, SQLModel, create_engine


class Transport(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, str_min_length=1)

    type: Literal["train", "flight", "bus"]
    name: str
    number: str | None = None
    departure_point: str
    arrival_point: str
    departure_time: NaiveDatetime
    arrival_time: NaiveDatetime
    purchase_url: HttpUrl | None = None
    purchased: bool = False


class Stay(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, str_min_length=1)

    hotel: str
    city: str
    address: str
    check_in: date
    check_out: date
    purchase_url: HttpUrl | None = None
    booked: bool = False


class Trip(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, str_min_length=1)

    origin: str
    destination: str
    outbound: Transport
    inbound: Transport
    stays: list[Stay]

    def issues(self) -> list[str]:
        issues = []
        out, back = self.outbound, self.inbound
        if not (
            out.departure_time
            < out.arrival_time
            < back.departure_time
            < back.arrival_time
        ):
            issues.append("往返出发和抵达时间必须依次递增（全部使用北京时间）。")
        if self.origin == self.destination:
            issues.append("出发地与目的地不能相同。")
        for leg in (out, back):
            if not leg.purchased and leg.purchase_url is None:
                issues.append(f"{leg.name} 尚未购买，缺少购买链接。")

        first, last = out.arrival_time.date(), back.departure_time.date()
        nights: dict[date, int] = {}
        for stay in self.stays:
            if not (first <= stay.check_in < stay.check_out <= last):
                issues.append(
                    f"{stay.hotel} 入住/退房日期须位于抵达日与返程出发日之间，且退房晚于入住。"
                )
                continue
            if not stay.booked and stay.purchase_url is None:
                issues.append(f"{stay.hotel} 尚未预订，缺少购买链接。")
            day = stay.check_in
            while day < stay.check_out:
                nights[day] = nights.get(day, 0) + 1
                day += timedelta(days=1)
        day = first
        while day < last:
            if nights.get(day, 0) != 1:
                issues.append(f"{day} 晚住宿缺失或重复，请保证恰好一处住宿。")
            day += timedelta(days=1)
        return issues


class TripRecord(SQLModel, table=True):
    """数据库记录；完整旅行方案仍由 Trip 校验并序列化为 JSON。"""

    __tablename__ = "trips"

    conversation_id: str = Field(primary_key=True)
    data: str = Field(sa_type=Text)


@dataclass
class TripStore:
    """按会话保存确认安排；配置 database 时持久化，测试默认使用内存。"""

    confirmed: dict[str, Trip] = field(default_factory=dict)
    database: Path | None = None
    _engine: Engine | None = field(default=None, init=False, repr=False)

    def __post_init__(self):
        if self.database is not None:
            # 与官方 Store 共用 SQLite 文件，每个 Session 结束后关闭连接。
            self._engine = create_engine(
                URL.create("sqlite", database=str(self.database)), poolclass=NullPool
            )
            SQLModel.metadata.create_all(self._engine)

    def save(self, conversation_id: str, trip: Trip) -> None:
        if self._engine is None:
            self.confirmed[conversation_id] = trip
        else:
            with Session(self._engine) as session:
                session.merge(
                    TripRecord(
                        conversation_id=conversation_id, data=trip.model_dump_json()
                    )
                )
                session.commit()

    def get(self, conversation_id: str) -> Trip | None:
        if self._engine is None:
            return self.confirmed.get(conversation_id)
        with Session(self._engine) as session:
            record = session.get(TripRecord, conversation_id)
            return Trip.model_validate_json(record.data) if record is not None else None

    def delete(self, conversation_id: str) -> None:
        if self._engine is None:
            self.confirmed.pop(conversation_id, None)
        else:
            with Session(self._engine) as session:
                record = session.get(TripRecord, conversation_id)
                if record is not None:
                    session.delete(record)
                    session.commit()
