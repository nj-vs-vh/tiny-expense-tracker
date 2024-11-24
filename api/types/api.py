import pydantic

from api.types.currency import Currency
from api.types.datetime import Datetime
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


class ReportPoolStats(pydantic.BaseModel):
    pool: StoredMoneyPool
    total: MoneySum
    fractions: dict[Currency, float]


class ReportPoolSnapshot(pydantic.BaseModel):
    timestamp: Datetime
    pool_stats: list[ReportPoolStats]
    overall_total: MoneySum


class ReportTagNetTotal(pydantic.BaseModel):
    tag: str | None
    total: MoneySum


class ReportApiRouteResponse(pydantic.BaseModel):
    snapshots: list[ReportPoolSnapshot]
    spent: MoneySum
    made: MoneySum
    tag_totals: list[ReportTagNetTotal]


class LoginLinkResponse(pydantic.BaseModel):
    url: str
    start_param: str
