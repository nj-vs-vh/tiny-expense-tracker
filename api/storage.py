import abc

from api.types import UserId
from api.types.money_pool import MoneyPool, MoneyPoolId
from api.types.transaction import Transaction, TransactionFilter


class Storage(abc.ABC):
    async def add_pool(self, user_id: UserId, new_pool: MoneyPool) -> None: ...

    async def load_pools(self, user_id: UserId) -> list[MoneyPool]: ...

    async def load_pool(
        self, user_id: UserId, pool_id: MoneyPoolId
    ) -> MoneyPool | None: ...

    async def add_transaction(self, user_id: str, transaction: Transaction) -> None: ...

    async def load_transactions(
        self, user_id: UserId, filter: TransactionFilter | None, offset: int, count: int
    ) -> list[Transaction]: ...


class InmemoryStorage(Storage):
    def __init__(self) -> None:
        self._user_transactions: dict[UserId, list[Transaction]] = {}
        self._user_pools: dict[UserId, list[MoneyPool]] = {}

    async def add_pool(self, user_id: UserId, new_pool: MoneyPool) -> None:
        self._user_pools.setdefault(user_id, []).append(new_pool)

    async def load_pools(self, user_id: UserId) -> list[MoneyPool]:
        return self._user_pools.get(user_id, [])

    async def load_pool(
        self, user_id: UserId, pool_id: MoneyPoolId
    ) -> MoneyPool | None:
        user_pools = await self.load_pools(user_id)
        matching_pool = next(p for p in user_pools if p.id == pool_id)
        if matching_pool:
            matching_pool
        else:
            return None

    async def load_transactions(
        self, user_id: UserId, filter: TransactionFilter | None, offset: int, count: int
    ) -> list[Transaction]:
        transactions = self._user_transactions.get(user_id, [])
        if filter is not None:
            transactions = [t for t in transactions if filter.matches(t)]
        return transactions[-offset - count - 1 : -offset - 1]
