import datetime

import pydantic

from api.types.ids import MoneyPoolId
from api.types.money_sum import MoneySum
from api.types.transaction import Transaction
from api.types.datetime import Datetime


class MoneyPool(pydantic.BaseModel):
    display_name: str
    balance: list[MoneySum]

    # optional fields
    is_visible: bool = True
    last_updated: Datetime | None = None
    display_color: str | None = None  # css color for frontend

    def update_with_transaction(self, transaction: Transaction) -> tuple[int, MoneySum]:
        matching = [
            (idx, s)
            for idx, s in enumerate(self.balance)
            if s.currency == transaction.sum.currency
        ]
        if not matching:
            raise ValueError(
                "Transaction is in currency not present in the pool, apply exchange rates first"
            )
        updated_sum_idx, updated_sum = matching[0]
        updated_sum.amount += transaction.sum.amount
        self.last_updated = datetime.datetime.now(tz=datetime.UTC)
        return updated_sum_idx, updated_sum


class StoredMoneyPool(MoneyPool):
    id: MoneyPoolId

    @classmethod
    def from_money_pool(cls, mp: MoneyPool, id: MoneyPoolId) -> "StoredMoneyPool":
        return StoredMoneyPool(id=id, **mp.model_dump())
