"""旅行商品备选及其展示数据。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


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
