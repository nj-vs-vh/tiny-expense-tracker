from typing import Annotated, Any

import pydantic

from api.iso4217 import CURRENCIES
from api.types.currency_iso4217 import CurrencyISO4217


def parse_currency(v: Any) -> CurrencyISO4217:
    if isinstance(v, CurrencyISO4217):
        return v
    if not isinstance(v, str):
        raise TypeError(
            f"currency value must be a string containing three-letter ISO2417 code"
        )
    if v not in CURRENCIES:
        raise ValueError(f"not a valid ISO 4217 code: {v}")
    return CURRENCIES[v]


def dump_currency(c: CurrencyISO4217):
    return c.code


Currency = Annotated[
    CurrencyISO4217,
    pydantic.BeforeValidator(parse_currency),
    pydantic.PlainSerializer(dump_currency, return_type=str),
]
