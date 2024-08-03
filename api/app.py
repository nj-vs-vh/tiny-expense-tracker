import datetime
import logging
from contextlib import asynccontextmanager
from decimal import Decimal
from typing import Annotated, Literal

import pydantic
from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import PlainTextResponse

from api.auth import Auth
from api.exchange_rates import ExchangeRates
from api.storage import Storage
from api.types.api import MoneyPoolIdResponse, SyncBalanceRequestBody, TransferMoneyRequestBody
from api.types.ids import MoneyPoolId, UserId
from api.types.money_pool import MoneyPool
from api.types.money_sum import MoneySum
from api.types.transaction import StoredTransaction, Transaction

logger = logging.getLogger(__name__)

Offset = Annotated[int, pydantic.Field(ge=0)]
Count = Annotated[int, pydantic.Field(ge=1, le=200)]

Ok = Literal["OK"]


async def coerce_to_pool(
    transaction: Transaction, pool: MoneyPool, exchange_rates: ExchangeRates
) -> None:
    if transaction.sum.currency in [sum.currency for sum in pool.balance]:
        return
    transaction.original_currency = transaction.sum.currency
    rate = await exchange_rates.get_rate(
        base=transaction.original_currency,
        target=pool.balance[0].currency,
    )
    transaction.sum = MoneySum(
        amount=Decimal(float(transaction.sum.amount) * rate.rate),
        currency=rate.target,
    )


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

    app = FastAPI(title="tiny-expense-tracker-api", lifespan=lifespan)

    AuthorizedUser = Annotated[UserId, Depends(auth.authorize_request)]

    @app.get("/")
    async def ping() -> dict[str, str]:
        return {"message": "Hi"}

    @app.post("/pools")
    async def create_pool(user_id: AuthorizedUser, new_pool: MoneyPool) -> MoneyPoolIdResponse:
        pool_id = await storage.add_pool(user_id=user_id, new_pool=new_pool)
        return {"id": pool_id}

    @app.get("/pools")
    async def get_pools(user_id: AuthorizedUser) -> dict[MoneyPoolId, MoneyPool]:
        return await storage.load_pools(user_id=user_id)

    @app.get("/pools/{pool_id}")
    async def get_pool(user_id: AuthorizedUser, pool_id: str) -> MoneyPool:
        pool = await storage.load_pool(user_id=user_id, pool_id=pool_id)
        if pool is None:
            raise HTTPException(status_code=404, detail="Pool not found")
        else:
            return pool

    @app.put("/pools/{pool_id}", response_class=PlainTextResponse)
    async def modify_pool(user_id: AuthorizedUser, pool_id: str, is_visible: bool | None) -> Ok:
        pool = await storage.load_pool(user_id=user_id, pool_id=pool_id)
        if pool is None:
            raise HTTPException(status_code=404, detail="Pool not found")
        if is_visible is not None:
            await storage.set_pool_visibility(user_id, pool_id=pool_id, is_visible=is_visible)
        # nothing more to do
        return "OK"

    @app.post("/transactions", response_class=PlainTextResponse)
    async def add_transaction(user_id: AuthorizedUser, transaction: Transaction) -> Ok:
        money_pool = await storage.load_pool(user_id=user_id, pool_id=transaction.pool_id)
        if money_pool is None:
            raise HTTPException(
                status_code=400,
                detail="Transaction is attributed to non-existent money pool",
            )
        await coerce_to_pool(transaction, money_pool, exchange_rates)
        await storage.add_transaction(user_id=user_id, transaction=transaction)
        return "OK"

    @app.get("/transactions")
    async def get_transactions(
        user_id: AuthorizedUser, offset: Offset = 0, count: Count = 10
    ) -> list[StoredTransaction]:
        return await storage.load_transactions(
            user_id=user_id, filter=None, offset=offset, count=count
        )

    @app.delete("/transactions/{transaction_id}", response_class=PlainTextResponse)
    async def delete_transaction(user_id: AuthorizedUser, transaction_id: str) -> Ok:
        if await storage.delete_transaction(user_id=user_id, transaction_id=transaction_id):
            return "OK"
        else:
            raise HTTPException(status_code=404, detail="No such transaction")

    @app.post("/transfer", response_class=PlainTextResponse)
    async def make_transfer(user_id: AuthorizedUser, body: TransferMoneyRequestBody) -> Ok:
        if body.sum.amount.is_zero():
            raise HTTPException(status_code=400, detail="Transfer amount can't be zero")

        from_pool = await storage.load_pool(user_id=user_id, pool_id=body.from_pool)
        to_pool = await storage.load_pool(user_id=user_id, pool_id=body.to_pool)
        if from_pool is None or to_pool is None:
            raise HTTPException(
                status_code=400,
                detail="Transfer from/to non-existent pool(s)",
            )

        added = body.sum
        added.amount = abs(added.amount)
        deducted = MoneySum(amount=-added.amount, currency=added.currency)

        transaction_deduct = Transaction(
            sum=deducted,
            pool_id=body.from_pool,
            # NOTE: not a bug - use the positive amount for display
            description=f"Transfer {added} to {to_pool.display_name} ({body.description})",
        )
        await coerce_to_pool(transaction_deduct, from_pool, exchange_rates)
        transaction_add = Transaction(
            sum=added,
            pool_id=body.to_pool,
            description=f"Transfer {added} from {from_pool.display_name} ({body.description})",
        )
        await coerce_to_pool(transaction_add, to_pool, exchange_rates)

        deduct_transaction = await storage.add_transaction(user_id, transaction_deduct)
        try:
            await storage.add_transaction(user_id, transaction_add)
        except Exception:
            logger.exception("Error making second transaction, trying to revert the first")
            try:
                if await storage.delete_transaction(user_id, transaction_id=deduct_transaction.id):
                    raise HTTPException(
                        status_code=503,
                        detail="Failed to make the transfer, but the state should be consistent",
                    )
            except Exception:
                logger.exception("Error deleting first transaction, the state is inconsistent")
            raise HTTPException(
                status_code=503,
                detail="Failed to make the transfer and the state might be inconsisten",
            )
        return "OK"

    @app.post("/sync-balance/{pool_id}", response_class=PlainTextResponse)
    async def sync_pool_balance(
        user_id: AuthorizedUser, pool_id: str, body: SyncBalanceRequestBody
    ) -> Ok:
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
            new_sum = MoneySum(amount=Decimal(new_amount), currency=old_sum.currency)
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
