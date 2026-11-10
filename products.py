"""查询结果中可由用户自行预订的旅游商品。"""

from typing import Annotated

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


def present_products(
    products: Annotated[list[Product], Field(min_length=1)],
) -> list[Product]:
    """在当前叙述位置展示已查到的酒店、门票、大巴等可预订商品卡片，不展示火车票或机票。

    先查询并核实商品，使用结果中的真实预订链接和对应图片；无可靠图片或价格时留空。
    展示前用简短文字引出推荐，展示后继续说明比较或询问用户偏好，正文不再重复图片和预订链接。
    此工具只展示商品，不代表用户已选定、确认或购买，不结束本轮咨询。
    """
    return products
