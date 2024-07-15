from typing import TypedDict

import pydantic

UserId = str
MoneyPoolId = str


class MoneyPoolIdResponse(TypedDict):
    id: MoneyPoolId


class SyncBalanceRequestBody(pydantic.BaseModel):
    amounts: list[float]
