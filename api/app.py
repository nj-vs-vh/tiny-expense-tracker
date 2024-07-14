from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException
import pydantic

from api.auth import Auth
from api.exchange_rates import ExchangeRates
from api.storage import Storage
from api.types import MoneyPoolIdResponse, UserId
from api.types.money_pool import MoneyPool, MoneyPoolId
from api.types.transaction import Transaction

Offset = Annotated[int, pydantic.Field(ge=0)]
Count = Annotated[int, pydantic.Field(ge=1, le=200)]


async def coerce_to_pool(
    transaction: Transaction,
    pool: MoneyPool,
    exchange_rates: ExchangeRates,
) -> None:
    if transaction.sum.currency in [sum.currency for sum in pool.balance]:
        return
    transaction.original_currency = transaction.sum.currency
    transaction.sum = exchange_rates.convert(transaction.sum, pool.balance[0].currency)


def create_app(storage: Storage, auth: Auth, exchange_rates: ExchangeRates) -> FastAPI:
    app = FastAPI()

    AthorizedUser = Annotated[UserId, Depends(auth.authorize_request)]

    @app.post("/pools")
    async def create_pool(
        user_id: AthorizedUser, new_pool: MoneyPool
    ) -> MoneyPoolIdResponse:
        pool_id = await storage.add_pool(user_id=user_id, new_pool=new_pool)
        return {"id": pool_id}

    @app.get("/pools")
    async def get_pools(user_id: AthorizedUser) -> dict[MoneyPoolId, MoneyPool]:
        return await storage.load_pools(user_id=user_id)

    @app.get("/pools/{pool_id}")
    async def get_pools(user_id: AthorizedUser, pool_id: str) -> MoneyPool:
        pool = await storage.load_pool(user_id=user_id, pool_id=pool_id)
        if pool is None:
            raise HTTPException(status_code=404, detail="Pool not found")
        else:
            return pool

    @app.post("/transactions")
    async def add_transaction(user_id: AthorizedUser, transaction: Transaction):
        money_pool = await storage.load_pool(
            user_id=user_id, pool_id=transaction.pool_id
        )
        if money_pool is None:
            raise HTTPException(
                status_code=400,
                detail="Transaction is attributed to non-existent money pool",
            )
        await coerce_to_pool(transaction, money_pool, exchange_rates)
        await storage.add_transaction(user_id=user_id, transaction=transaction)

    @app.get("/transactions")
    async def get_transactions(
        user_id: AthorizedUser, offset: Offset = 0, count: Count = 10
    ) -> list[Transaction]:
        return await storage.load_transactions(
            user_id=user_id, filter=None, offset=offset, count=count
        )

    return app
