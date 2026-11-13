"""账号接口的数据校验。"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, SecretStr, StringConstraints

Username = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        to_lower=True,
        min_length=1,
        max_length=64,
        pattern=r"^[a-zA-Z0-9_.-]+$",
    ),
]
Password = Annotated[SecretStr, StringConstraints(min_length=8, max_length=128)]


class Login(BaseModel):
    username: Username
    password: Annotated[SecretStr, StringConstraints(min_length=1, max_length=128)]


class Refresh(BaseModel):
    refresh_token: Annotated[
        SecretStr, StringConstraints(min_length=1, max_length=4096)
    ]


class ChangePassword(BaseModel):
    old_password: SecretStr
    new_password: Password


class UserInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    username: str


class TokenPayload(BaseModel):
    model_config = ConfigDict(strict=True)
    sub: Annotated[str, StringConstraints(min_length=1)]
    sid: Annotated[str, StringConstraints(min_length=1)]
    type: Literal["access", "refresh"]
    exp: int
    jti: Annotated[str, StringConstraints(min_length=1)]


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"
