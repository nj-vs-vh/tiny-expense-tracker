import copy
import datetime
import logging
from contextlib import asynccontextmanager
from decimal import Decimal
from typing import Annotated, Iterable, Literal

import pydantic
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse

from api.auth import Auth
from api.exchange_rates import ExchangeRates
from api.storage import Storage
from api.types.api import (
    MainApiRouteResponse,
    MoneyPoolAttributesUpdate,
    ReportApiRouteResponse,
    ReportPoolSnapshot,
    ReportPoolStats,
    SyncBalanceRequestBody,
    TransferMoneyRequestBody,
)
from api.types.currency import Currency, CurrencyAdapter
from api.types.datetime import Datetime
from api.types.ids import UserId
from api.types.money_pool import MoneyPool, StoredMoneyPool
from api.types.money_sum import MoneySum
from api.types.transaction import StoredTransaction, Transaction, TransactionFilter

logger = logging.getLogger(__name__)

Offset = Annotated[int, pydantic.Field(ge=0)]
Count = Annotated[int, pydantic.Field(ge=1, le=200)]
ReportPoints = Annotated[int, pydantic.Field(ge=1, le=60)]

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


async def pool_total(
    pool: MoneyPool, exchange_rates: ExchangeRates, target_currency: Currency
) -> tuple[MoneySum, dict[Currency, float]]:
    contributions: dict[Currency, float] = {}
    for sum_ in pool.balance:
        rate = await exchange_rates.get_rate(base=sum_.currency, target=target_currency)
        contributions[sum_.currency] = float(sum_.amount) * rate.rate
    total_amount = sum(p for p in contributions.values())
    total = MoneySum(amount=Decimal(total_amount), currency=target_currency)
    total.round_for_currency()
    fractions = {c: p / total_amount for c, p in contributions.items()}
    return total, fractions


async def sum_transactions(
    transactions: Iterable[Transaction], exchange_rates: ExchangeRates, target_currency: Currency
) -> MoneySum:
    total_amt = 0.0
    for t in transactions:
        rate = await exchange_rates.get_rate(base=t.sum.currency, target=target_currency)
        total_amt += float(t.sum.amount) * rate.rate
    return MoneySum(
        amount=Decimal(total_amt),
        currency=target_currency,
    )


def create_app(
    storage: Storage,
    auth: Auth,
    exchange_rates: ExchangeRates,
    frontend_origins: list[str] | None = None,
) -> FastAPI:

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        logger.info("Running lifespan methods")
        await storage.initialize()
        logger.info("Storage initialized")
        await auth.initialize()
        logger.info("Auth initialized")
        await exchange_rates.initialize()
        logger.info("Exchange rates initialized")
        yield
        # logger.info("Nothing to cleanup, bye")

    app = FastAPI(title="tiny-expense-tracker-api", lifespan=lifespan)

    if frontend_origins is not None:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=frontend_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    AuthorizedUser = Annotated[UserId, Depends(auth.authorize_request)]
    auth.setup_login_routes(app)

    @app.get("/")
    async def ping() -> dict[str, str]:
        return {"message": "Hi"}

    @app.get("/main")
    async def main_api_route(user_id: AuthorizedUser) -> MainApiRouteResponse:
        pools = await storage.load_pools(user_id)
        last_transactions = await storage.load_transactions(
            user_id, filter=None, offset=0, count=30
        )
        return MainApiRouteResponse(
            pools=pools,
            last_transactions=last_transactions,
        )

    @app.get("/report")
    async def generate_report(
        user_id: AuthorizedUser,
        start: Datetime,
        end: Datetime | None = None,
        points: ReportPoints = 30,
        target_currency: str = "EUR",
    ) -> ReportApiRouteResponse:
        if start.tzinfo is None or (end is not None and end.tzinfo is None):
            raise HTTPException(
                status_code=400, detail="All datetimes must have timezone info specified"
            )
        target_currency_: Currency = CurrencyAdapter.validate_python(target_currency)
        pools = await storage.load_pools(user_id)
        current_pools_by_id = {p.id: p for p in pools}

        # first, reverting pools to their state at end time
        if end is not None:
            transactions_after_end = await storage.load_transactions(
                user_id,
                filter=TransactionFilter(min_timestamp=end),
                offset=0,
                count=10_000,
            )
            for t in transactions_after_end:
                current_pools_by_id[t.pool_id].update_with_transaction(t.inverted())

        # now, loading transactions in the period of interest
        end_dt = end or datetime.datetime.now(tz=datetime.UTC)
        transactions = await storage.load_transactions(
            user_id,
            filter=TransactionFilter(min_timestamp=start, max_timestamp=end_dt),
            offset=0,
            count=1000,
        )
        timestep = (end_dt.timestamp() - start.timestamp()) / (points - 1)
        snapshot_dts = [
            end_dt - datetime.timedelta(seconds=timestep * steps) for steps in range(points)
        ]
        snapshot_pools = [copy.deepcopy(list(current_pools_by_id.values()))]
        # going over transactions latest to earliest, applying
        transactions.sort(key=lambda t: t.timestamp, reverse=True)
        for t in transactions:
            if t.timestamp < snapshot_dts[len(snapshot_pools)]:
                snapshot_pools.append(copy.deepcopy(list(current_pools_by_id.values())))
            current_pools_by_id[t.pool_id].update_with_transaction(t.inverted())
        missing_snapshots_count = len(snapshot_dts) - len(snapshot_pools)
        for _ in range(missing_snapshots_count):
            snapshot_pools.append(copy.deepcopy(list(current_pools_by_id.values())))

        snapshots: list[ReportPoolSnapshot] = []
        for dt, pools in zip(snapshot_dts, snapshot_pools):
            overall_total = MoneySum(amount=Decimal(0), currency=target_currency_)
            pool_stats: list[ReportPoolStats] = []
            for pool in pools:
                pool_total_, fractions = await pool_total(
                    pool, exchange_rates, target_currency=target_currency_
                )
                pool_stats.append(
                    ReportPoolStats(pool=pool, total=pool_total_, fractions=fractions)
                )
                overall_total.amount += pool_total_.amount
            snapshots.append(
                ReportPoolSnapshot(
                    timestamp=dt,
                    pool_stats=pool_stats,
                    overall_total=overall_total,
                )
            )
        return ReportApiRouteResponse(
            snapshots=snapshots,
            spent=await sum_transactions(
                transactions=(t.inverted() for t in transactions if t.sum.amount < 0),
                exchange_rates=exchange_rates,
                target_currency=target_currency_,
            ),
            made=await sum_transactions(
                transactions=(t for t in transactions if t.sum.amount > 0),
                exchange_rates=exchange_rates,
                target_currency=target_currency_,
            ),
        )

    @app.post("/pools")
    async def create_pool(user_id: AuthorizedUser, new_pool: MoneyPool) -> StoredMoneyPool:
        return await storage.add_pool(user_id=user_id, new_pool=new_pool)

    @app.get("/pools")
    async def get_pools(user_id: AuthorizedUser) -> list[StoredMoneyPool]:
        return await storage.load_pools(user_id=user_id)

    @app.get("/pools/{pool_id}")
    async def get_pool(user_id: AuthorizedUser, pool_id: str) -> StoredMoneyPool:
        pool = await storage.load_pool(user_id=user_id, pool_id=pool_id)
        if pool is None:
            raise HTTPException(status_code=404, detail="Pool not found")
        else:
            return pool

    @app.put("/pools/{pool_id}", response_class=PlainTextResponse)
    async def modify_pool(
        user_id: AuthorizedUser, pool_id: str, update: MoneyPoolAttributesUpdate
    ) -> Ok:
        if await storage.set_pool_attributes(user_id, pool_id=pool_id, update=update):
            return "OK"
        else:
            raise HTTPException(status_code=404, detail="Pool not found")

    @app.post("/transactions")
    async def add_transaction(
        user_id: AuthorizedUser, transaction: Transaction
    ) -> StoredTransaction:
        money_pool = await storage.load_pool(user_id=user_id, pool_id=transaction.pool_id)
        if money_pool is None:
            raise HTTPException(
                status_code=400,
                detail="Transaction is attributed to non-existent money pool",
            )
        await coerce_to_pool(transaction, money_pool, exchange_rates)
        return await storage.add_transaction(user_id=user_id, transaction=transaction)

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
