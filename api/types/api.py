import pydantic

from api.types.ids import MoneyPoolId
from api.types.money_pool import StoredMoneyPool
from api.types.money_sum import MoneySum
from api.types.transaction import StoredTransaction


class MoneyPoolAttributesUpdate(pydantic.BaseModel):
    is_visible: bool | None = None
    display_name: str | None = None
    display_color: str | None = None


class SyncBalanceRequestBody(pydantic.BaseModel):
    amounts: list[float]


class TransferMoneyRequestBody(pydantic.BaseModel):
    from_pool: MoneyPoolId
    to_pool: MoneyPoolId
    sum: MoneySum
    description: str


class MainApiRouteResponse(pydantic.BaseModel):
    pools: list[StoredMoneyPool]
    last_transactions: list[StoredTransaction]
