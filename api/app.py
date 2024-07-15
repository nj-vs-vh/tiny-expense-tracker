import datetime
import logging
from contextlib import asynccontextmanager
from typing import Annotated

import pydantic
from fastapi import Depends, FastAPI, Header, HTTPException

from api.auth import Auth
from api.exchange_rates import ExchangeRates
from api.storage import Storage
from api.types import MoneyPoolId, MoneyPoolIdResponse, SyncBalanceRequestBody, UserId
from api.types.money_pool import MoneyPool
from api.types.money_sum import MoneySum
from api.types.transaction import Transaction

logger = logging.getLogger(__name__)

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

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        logger.info("Running lifespan methods")
        await storage.initialize()
        logger.info("Storage initialized")
        await exchange_rates.initialize()
        logger.info("Exchange rates initialized")
        yield
        logger.info("Nothing to cleanup, bye")

    app = FastAPI(lifespan=lifespan)

    AuthorizedUser = Annotated[UserId, Depends(auth.authorize_request)]

    @app.post("/pools")
    async def create_pool(user_id: AuthorizedUser, new_pool: MoneyPool) -> MoneyPoolIdResponse:
        pool_id = await storage.add_pool(user_id=user_id, new_pool=new_pool)
        return {"id": pool_id}

    @app.get("/pools")
    async def get_pools(user_id: AuthorizedUser) -> dict[MoneyPoolId, MoneyPool]:
        return await storage.load_pools(user_id=user_id)

    @app.get("/pools/{pool_id}")
    async def get_specific_pool(user_id: AuthorizedUser, pool_id: str) -> MoneyPool:
        pool = await storage.load_pool(user_id=user_id, pool_id=pool_id)
        if pool is None:
            raise HTTPException(status_code=404, detail="Pool not found")
        else:
            return pool

    @app.post("/transactions")
    async def add_transaction(user_id: AuthorizedUser, transaction: Transaction):
        money_pool = await storage.load_pool(user_id=user_id, pool_id=transaction.pool_id)
        if money_pool is None:
            raise HTTPException(
                status_code=400,
                detail="Transaction is attributed to non-existent money pool",
            )
        await coerce_to_pool(transaction, money_pool, exchange_rates)
        await storage.add_transaction(user_id=user_id, transaction=transaction)

    @app.get("/transactions")
    async def get_transactions(
        user_id: AuthorizedUser, offset: Offset = 0, count: Count = 10
    ) -> list[Transaction]:
        return await storage.load_transactions(
            user_id=user_id, filter=None, offset=offset, count=count
        )

    @app.post("/sync-balance/{pool_id}")
    async def sync_pool_balance(
        user_id: AuthorizedUser, pool_id: str, body: SyncBalanceRequestBody
    ) -> str:
        pool = await storage.load_pool(user_id, pool_id)
        if pool is None:
            raise HTTPException(404, detail="Pool not found")
        if len(pool.balance) != len(body.amounts):
            raise HTTPException(
                400,
                detail=f"New amount for every currency in the pool expected ({len(pool.balance)})",
            )

        errors: list[Exception] = []
        for old_sum, new_amount in zip(pool.balance, body.amounts):
            new_sum = MoneySum(amount=new_amount, currency=old_sum.currency)
            delta = new_sum.amount - old_sum.amount
            if not delta:
                continue
            try:
                await storage.add_transaction(
                    user_id=user_id,
                    transaction=Transaction(
                        timestamp=datetime.datetime.now(),
                        sum=MoneySum(amount=delta, currency=old_sum.currency),
                        pool_id=pool_id,
                        description=f"{pool.display_name} synced {old_sum.amount} -> {new_sum.amount} {old_sum.currency}",
                        is_diffuse=True,
                    ),
                )
            except Exception as e:
                logger.exception(f"Error syncing {old_sum} -> {new_sum}")
                errors.append(e)

        if errors:
            if len(errors) == len(pool.balance):
                raise HTTPException(
                    503,
                    detail="Failed to save transactions",
                )
            else:
                raise HTTPException(
                    503,
                    detail="Failed to save some transactions, sync might be incomplete",
                )
        return "OK"

    return app
