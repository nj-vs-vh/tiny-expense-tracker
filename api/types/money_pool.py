import pydantic

from api.types.money_sum import MoneySum

MoneyPoolId = str


class MoneyPool(pydantic.BaseModel):
    display_name: str
    balance: list[MoneySum]
