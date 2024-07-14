from api.types.currency import Currency
from api.types.money_sum import MoneySum


MoneyPoolId = str


class MoneyPool:
    id: str
    display_name: str
    balance: MoneySum
