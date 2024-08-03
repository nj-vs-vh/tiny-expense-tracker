import datetime

import pydantic

from api.types.currency import Currency
from api.types.datetime import Datetime
from api.types.ids import MoneyPoolId, TransactionId
from api.types.money_sum import MoneySum


class Transaction(pydantic.BaseModel):
    sum: MoneySum
    pool_id: MoneyPoolId
    description: str
    timestamp: Datetime = pydantic.Field(default_factory=datetime.datetime.now)

    # diffuse = a transaction implying any number of actual transactions too small to be tracked
    is_diffuse: bool = False

    # for transactions made not in pool's currency
    original_currency: Currency | None = None


class StoredTransaction(Transaction):
    id: TransactionId

    @classmethod
    def from_transaction(cls, t: Transaction, id: TransactionId) -> "StoredTransaction":
        return StoredTransaction(id=id, **t.model_dump())


class TransactionFilter(pydantic.BaseModel):
    min_timestamp: Datetime | None = None
    max_timestamp: Datetime | None = None
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
