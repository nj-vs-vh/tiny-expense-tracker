from typing import TypedDict

from api.types.money_pool import MoneyPoolId


UserId = str

class MoneyPoolIdResponse(TypedDict):
    id: MoneyPoolId
