"""直达、单城市旅行的基础安排；只保存用户明确确认的方案。"""

import sqlite3
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, HttpUrl, NaiveDatetime


class Transport(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, str_min_length=1)

    type: Literal["train", "flight"]
    number: str
    departure_city: str
    arrival_city: str
    departure_station: str
    arrival_station: str
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
        if (
            out.departure_city != back.arrival_city
            or out.arrival_city != back.departure_city
            or out.departure_city == out.arrival_city
        ):
            issues.append("仅支持单目的城市往返，回程城市方向须与去程相反。")
        for leg in (out, back):
            if not leg.purchased and leg.purchase_url is None:
                issues.append(f"{leg.number} 尚未购买，缺少购买链接。")

        first, last = out.arrival_time.date(), back.departure_time.date()
        nights: dict[date, int] = {}
        for stay in self.stays:
            if stay.city != out.arrival_city:
                issues.append(f"{stay.hotel} 不在目的城市。")
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


@dataclass
class TripStore:
    """按会话保存确认安排；配置 database 时持久化，测试默认使用内存。"""

    confirmed: dict[str, Trip] = field(default_factory=dict)

    database: Path | None = None

    def __post_init__(self):
        if self.database:
            with sqlite3.connect(self.database) as conn:
                conn.execute(
                    "CREATE TABLE IF NOT EXISTS trips (conversation_id TEXT PRIMARY KEY, data TEXT NOT NULL)"
                )

    def save(self, conversation_id: str, trip: Trip) -> None:
        if self.database is None:
            self.confirmed[conversation_id] = trip
        else:
            with sqlite3.connect(self.database) as conn:
                conn.execute(
                    "INSERT INTO trips VALUES (?, ?) ON CONFLICT(conversation_id) DO UPDATE SET data=excluded.data",
                    (conversation_id, trip.model_dump_json()),
                )

    def get(self, conversation_id: str) -> Trip | None:
        if self.database is None:
            return self.confirmed.get(conversation_id)
        with sqlite3.connect(self.database) as conn:
            row = conn.execute(
                "SELECT data FROM trips WHERE conversation_id=?", (conversation_id,)
            ).fetchone()
        return Trip.model_validate_json(row[0]) if row else None

    def delete(self, conversation_id: str) -> None:
        if self.database is None:
            self.confirmed.pop(conversation_id, None)
        else:
            with sqlite3.connect(self.database) as conn:
                conn.execute(
                    "DELETE FROM trips WHERE conversation_id=?", (conversation_id,)
                )
