from typing import TypedDict

import pydantic

from api.types.ids import MoneyPoolId
from api.types.money_sum import MoneySum


class MoneyPoolIdResponse(TypedDict):
    id: MoneyPoolId


class SyncBalanceRequestBody(pydantic.BaseModel):
    amounts: list[float]


class TransferMoneyRequestBody(pydantic.BaseModel):
    from_pool: MoneyPoolId
    to_pool: MoneyPoolId
    sum: MoneySum
