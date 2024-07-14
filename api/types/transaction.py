import pydantic
import datetime

from api.types.money_pool import MoneyPoolId
from api.types.money_sum import MoneySum

TransactionId = str


class Transaction(pydantic.BaseModel):
    timestamp: datetime.datetime
    sum: MoneySum
    pool_id: MoneyPoolId
    description: str

    # diffuse = a transaction implying any number of actual transactions too small to be tracked
    is_diffuse: bool = False


class TransactionFilter(pydantic.BaseModel):
    min_timestamp: datetime.datetime | None = None
    max_timestamp: datetime.datetime | None = None
    pool_ids: list[MoneyPoolId] | None = None

    @classmethod
    def empty(cls) -> "TransactionFilter":
        return TransactionFilter()

    def matches(self, t: Transaction) -> bool:
        if self.min_timestamp is not None and t.timestamp < self.min_timestamp:
            return False
        if self.max_timestamp is not None and t.timestamp > self.max_timestamp:
            return False
        if self.pool_ids is not None and t.pool_id not in self.pool_ids:
            return False
        return True
