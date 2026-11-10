"""往返交通与住宿安排及其校验。"""

from datetime import date, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, HttpUrl, NaiveDatetime


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


class TravelArrangements(BaseModel):
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
