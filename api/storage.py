import abc
import uuid

from api.types import UserId
from api.types.money_pool import MoneyPool, MoneyPoolId
from api.types.money_sum import MoneySum
from api.types.transaction import Transaction, TransactionFilter


class Storage(abc.ABC):
    @abc.abstractmethod
    async def add_pool(self, user_id: UserId, new_pool: MoneyPool) -> MoneyPoolId: ...

    @abc.abstractmethod
    async def add_balance_to_pool(
        self, user_id: UserId, pool_id: MoneyPoolId, new_balance: MoneySum
    ) -> None: ...

    @abc.abstractmethod
    async def load_pools(self, user_id: UserId) -> dict[MoneyPoolId, MoneyPool]: ...

    @abc.abstractmethod
    async def load_pool(
        self, user_id: UserId, pool_id: MoneyPoolId
    ) -> MoneyPool | None: ...

    @abc.abstractmethod
    async def add_transaction(self, user_id: str, transaction: Transaction) -> None: ...

    @abc.abstractmethod
    async def load_transactions(
        self, user_id: UserId, filter: TransactionFilter | None, offset: int, count: int
    ) -> list[Transaction]: ...


class InmemoryStorage(Storage):
    def __init__(self) -> None:
        self._user_transactions: dict[UserId, list[Transaction]] = {}
        self._user_pools: dict[UserId, dict[MoneyPoolId, MoneyPool]] = {}

    async def add_pool(self, user_id: UserId, new_pool: MoneyPool) -> MoneyPoolId:
        pool_id = str(uuid.uuid4())
        self._user_pools.setdefault(user_id, {})[pool_id] = new_pool
        return pool_id

    async def add_balance_to_pool(
        self, user_id: UserId, pool_id: UserId, new_balance: MoneySum
    ) -> None:
        p = await self.load_pool(user_id, pool_id)
        if new_balance.currency not in [s.currency for s in p.balance]:
            p.balance.append(new_balance)
        else:
            raise ValueError(
                f"Balance already has currency {new_balance.currency.code}"
            )

    async def load_pools(self, user_id: UserId) -> dict[MoneyPoolId, MoneyPool]:
        return self._user_pools.get(user_id, {})

    async def load_pool(
        self, user_id: UserId, pool_id: MoneyPoolId
    ) -> MoneyPool | None:
        user_pools = await self.load_pools(user_id)
        return user_pools.get(pool_id)

    async def add_transaction(self, user_id: str, transaction: Transaction) -> None:
        self._user_transactions.setdefault(user_id, []).append(transaction)

    async def load_transactions(
        self, user_id: UserId, filter: TransactionFilter | None, offset: int, count: int
    ) -> list[Transaction]:
        transactions = self._user_transactions.get(user_id, [])
        if filter is not None:
            transactions = [t for t in transactions if filter.matches(t)]
        return transactions[-offset - count - 1 : -offset - 1]
