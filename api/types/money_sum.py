from decimal import Decimal
from typing import Self

import pydantic

from api.types.currency import Currency


class MoneySum(pydantic.BaseModel):
    amount: Decimal
    currency: Currency

    def __str__(self) -> str:
        return f"{self.amount} {self.currency.code}"

    def round_for_currency(self) -> None:
        self.amount = round(self.amount, ndigits=self.currency.precision)

    @pydantic.model_validator(mode="after")
    def amount_has_correct_precision(self) -> Self:
        self.round_for_currency()
        return self
