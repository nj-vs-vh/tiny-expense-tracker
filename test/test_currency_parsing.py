from decimal import Decimal
from typing import Any

import pytest

from api.iso4217 import CURRENCIES
from api.types.money_sum import MoneySum


@pytest.mark.parametrize(
    "raw, expected_money_sum",
    [
        pytest.param(
            {"amount": 14.3, "currency": "EUR"},
            MoneySum(amount=Decimal("14.30"), currency=CURRENCIES["EUR"]),
        ),
        pytest.param(
            {"amount": -14.3, "currency": "EUR"},
            MoneySum(amount=Decimal("-14.30"), currency=CURRENCIES["EUR"]),
        ),
        pytest.param(
            {"amount": 3.14152, "currency": "USD"},
            MoneySum(amount=Decimal("3.14"), currency=CURRENCIES["USD"]),
            id="rounding appropriate to the currency",
        ),
        pytest.param(
            {"amount": 3.14152, "currency": "VND"},
            MoneySum(amount=Decimal("3"), currency=CURRENCIES["VND"]),
            id="rounding appropriate to the currency",
        ),
    ],
)
def test_sum_parsing(raw: dict[str, Any], expected_money_sum: MoneySum):
    assert MoneySum.model_validate(raw) == expected_money_sum
