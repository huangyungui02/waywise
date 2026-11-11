"""多段交通与住宿安排及其校验。"""

from datetime import date, datetime, time, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


class Transport(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, str_min_length=1)

    type: Literal["train", "flight", "bus", "drive", "taxi", "ferry"]
    number: str | None = None
    departure_station: str
    arrival_station: str
    departure_time: datetime
    arrival_time: datetime
    purchase_url: HttpUrl | None = None
    purchased: bool = False

    @field_validator("departure_time", "arrival_time")
    @classmethod
    def beijing_time(cls, value: datetime) -> datetime:
        zone = ZoneInfo("Asia/Shanghai")
        return (
            value.replace(tzinfo=zone)
            if value.tzinfo is None
            else value.astimezone(zone)
        )


class Stay(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, str_min_length=1)

    hotel: str
    city: str
    address: str
    check_in: date
    check_out: date
    purchase_url: HttpUrl | None = None
    booked: bool = False


class TravelArrangements(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, str_min_length=1)

    transports: list[Transport] = Field(min_length=1)
    stays: list[Stay]

    def issues(self) -> list[str]:
        issues = []
        first, last = self.transports[0], self.transports[-1]
        for index, leg in enumerate(self.transports):
            if leg.departure_time >= leg.arrival_time:
                issues.append(
                    f"第 {index + 1} 段出发和抵达时间必须依次递增（全部使用北京时间）。"
                )
            if index:
                previous = self.transports[index - 1]
                if previous.arrival_time >= leg.departure_time:
                    issues.append(f"第 {index + 1} 段与上一段交通时间必须依次递增。")

        start = first.departure_time.date()
        end = max([last.arrival_time.date(), *(stay.check_out for stay in self.stays)])
        for stay in self.stays:
            if not (start <= stay.check_in < stay.check_out):
                issues.append(f"{stay.hotel} 入住日期不得早于出发日，且退房晚于入住。")
            if not stay.booked and stay.purchase_url is None:
                issues.append(f"{stay.hotel} 尚未预订，缺少购买链接。")

        day = start
        while day < end:
            midnight = datetime.combine(
                day + timedelta(days=1), time(), ZoneInfo("Asia/Shanghai")
            )
            overnight = any(
                leg.departure_time < midnight <= leg.arrival_time
                for leg in self.transports
            )
            stays = [
                stay for stay in self.stays if stay.check_in <= day < stay.check_out
            ]
            if len(stays) > 1:
                issues.append(f"{day} 晚住宿重复，请保证恰好一处住宿。")
            elif not stays and not overnight:
                issues.append(f"{day} 晚住宿缺失，请补齐酒店或跨夜交通。")
            day += timedelta(days=1)
        return issues
