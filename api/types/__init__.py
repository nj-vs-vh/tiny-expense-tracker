from typing import TypedDict

import pydantic

from api.types.money_pool import MoneyPoolId


UserId = str

class MoneyPoolIdResponse(TypedDict):
    id: MoneyPoolId


class SyncBalanceRequestBody(pydantic.BaseModel):
    amounts: list[float]
