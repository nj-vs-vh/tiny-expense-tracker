import pydantic

from api.types.money_sum import MoneySum
from api.types.transaction import Transaction


class MoneyPool(pydantic.BaseModel):
    display_name: str
    balance: list[MoneySum]

    is_visible: bool = True  # default for backwards compatibility

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
        return updated_sum_idx, updated_sum
