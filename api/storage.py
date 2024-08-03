import abc
import copy
import logging
import time
import uuid
from typing import Annotated, Any, Self, Type

import fastapi
import pydantic
from bson import ObjectId
from motor.motor_asyncio import (
    AsyncIOMotorClient,
    AsyncIOMotorClientSession,
    AsyncIOMotorCollection,
)

from api.types.ids import MoneyPoolId, TransactionId, UserId
from api.types.money_pool import MoneyPool
from api.types.money_sum import MoneySum
from api.types.transaction import StoredTransaction, Transaction, TransactionFilter


class Storage(abc.ABC):
    async def initialize(self) -> None:
        pass

    @abc.abstractmethod
    async def add_pool(self, user_id: UserId, new_pool: MoneyPool) -> MoneyPoolId: ...

    @abc.abstractmethod
    async def add_balance_to_pool(
        self, user_id: UserId, pool_id: MoneyPoolId, new_balance: MoneySum
    ) -> bool: ...

    @abc.abstractmethod
    async def load_pools(self, user_id: UserId) -> dict[MoneyPoolId, MoneyPool]: ...

    @abc.abstractmethod
    async def load_pool(self, user_id: UserId, pool_id: MoneyPoolId) -> MoneyPool | None: ...

    @abc.abstractmethod
    async def add_transaction(
        self, user_id: str, transaction: Transaction
    ) -> StoredTransaction: ...

    @abc.abstractmethod
    async def load_transactions(
        self, user_id: UserId, filter: TransactionFilter | None, offset: int, count: int
    ) -> list[StoredTransaction]: ...

    @abc.abstractmethod
    async def delete_transaction(self, user_id: UserId, transaction_id: TransactionId) -> bool: ...


class InmemoryStorage(Storage):
    """Lacks synchronization, only for testing purposes"""

    def __init__(self) -> None:
        self._user_transactions: dict[UserId, list[StoredTransaction]] = {}
        self._user_pools: dict[UserId, dict[MoneyPoolId, MoneyPool]] = {}

    async def add_pool(self, user_id: UserId, new_pool: MoneyPool) -> MoneyPoolId:
        pool_id = str(uuid.uuid4())
        self._user_pools.setdefault(user_id, {})[pool_id] = new_pool
        return pool_id

    async def add_balance_to_pool(
        self, user_id: UserId, pool_id: UserId, new_balance: MoneySum
    ) -> bool:
        p = await self.load_pool(user_id, pool_id)
        if p is None:
            return False
        if new_balance.currency not in [s.currency for s in p.balance]:
            p.balance.append(new_balance)
            return True
        else:
            raise ValueError(f"Balance already has currency {new_balance.currency.code}")

    async def load_pools(self, user_id: UserId) -> dict[MoneyPoolId, MoneyPool]:
        return self._user_pools.get(user_id, {})

    async def load_pool(self, user_id: UserId, pool_id: MoneyPoolId) -> MoneyPool | None:
        user_pools = await self.load_pools(user_id)
        return user_pools.get(pool_id)

    async def add_transaction(self, user_id: str, transaction: Transaction) -> StoredTransaction:
        pool = await self.load_pool(user_id, transaction.pool_id)
        if pool is None:
            raise ValueError("Transaction attributed to non-existent pool")
        pool.update_with_transaction(transaction)
        stored = StoredTransaction.from_transaction(transaction, id=str(uuid.uuid4()))
        self._user_transactions.setdefault(user_id, []).append(stored)
        return stored

    async def load_transactions(
        self, user_id: UserId, filter: TransactionFilter | None, offset: int, count: int
    ) -> list[StoredTransaction]:
        transactions = self._user_transactions.get(user_id, [])
        if filter is not None:
            transactions = [t for t in transactions if filter.matches(t)]
        end = len(transactions) - offset
        start = end - count - 1
        return transactions[start:end]

    async def delete_transaction(self, user_id: UserId, transaction_id: TransactionId) -> bool:
        user_transactions = self._user_transactions.get(user_id, [])
        matching_transactions = [t for t in user_transactions if t.id == transaction_id]
        if not matching_transactions:
            return False

        deleted = matching_transactions[0]
        deleted = copy.deepcopy(deleted)
        deleted.sum.amount = -deleted.sum.amount  # invert for pool updating purpose
        pool = await self.load_pool(user_id, deleted.pool_id)
        assert pool is not None
        pool.update_with_transaction(deleted)
        self._user_transactions[user_id] = [t for t in user_transactions if t.id != transaction_id]
        return True


def validate_object_id(v: Any) -> str:
    if isinstance(v, ObjectId):
        return str(v)
    else:
        raise ValueError("Must be an instance of bson.ObjectId class")


ObjectIdPydantic = Annotated[
    str,
    pydantic.BeforeValidator(validate_object_id),
    pydantic.WithJsonSchema({"type": "string"}),
]


class MongoStoredModel(pydantic.BaseModel):
    id: ObjectIdPydantic | None = pydantic.Field(alias="_id", default=None)


class OwnedPool(MongoStoredModel):
    pool: MoneyPool
    owner: UserId


class OwnedTransaction(MongoStoredModel):
    transaction: Transaction
    owner: UserId

    def to_stored_transaction(self) -> StoredTransaction:
        if self.id is None:
            raise ValueError(
                "Attempt to convert non-stored OwnedTransaction (no id attr) to StoredTransaction"
            )
        return StoredTransaction.from_transaction(self.transaction, id=self.id)


class MongoDbStorage(Storage):
    def __init__(self, url: str) -> None:
        self.client: AsyncIOMotorClient = AsyncIOMotorClient(url)
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        db = "tiny-expense-tracker"
        self.transactions_coll: AsyncIOMotorCollection = self.client[db].transactions
        self.pools_coll: AsyncIOMotorCollection = self.client[db].pools

    async def initialize(self) -> None:
        start = time.time()
        await self.client.admin.command("ping")
        self.logger.info(f"MongoDB pinged in {time.time() - start:.2} sec")
        # self.logger.info(f"transactions: {await self.transactions_coll.count_documents({})}")
        # self.logger.info(f"pools: {await self.pools_coll.count_documents({})}")

    async def add_pool(self, user_id: UserId, new_pool: MoneyPool) -> UserId:
        result = await self.pools_coll.insert_one(
            OwnedPool(pool=new_pool, owner=user_id).model_dump(mode="json")
        )
        return str(result.inserted_id)

    def _pool_filter(self, user_id: UserId, pool_id: MoneyPoolId) -> dict[str, Any]:
        if not ObjectId.is_valid(pool_id):
            # HACK: storage is not supposed to validate data in API, but I'm lazy now
            raise fastapi.HTTPException(404, "Invalid pool id")
        return {"_id": ObjectId(pool_id), "owner": user_id}

    async def _load_pool_internal(
        self, user_id: UserId, pool_id: MoneyPoolId, session: AsyncIOMotorClientSession | None
    ) -> MoneyPool | None:
        doc = await self.pools_coll.find_one(self._pool_filter(user_id, pool_id), session=session)
        if doc is None:
            return None
        return OwnedPool.model_validate(doc).pool

    async def load_pool(self, user_id: UserId, pool_id: UserId) -> MoneyPool | None:
        return await self._load_pool_internal(user_id, pool_id, session=None)

    async def load_pools(self, user_id: UserId) -> dict[str, MoneyPool]:
        cursor = self.pools_coll.find({"owner": user_id})
        docs = await cursor.to_list(length=1000)
        return {str(d["_id"]): OwnedPool.model_validate(d).pool for d in docs}

    async def add_balance_to_pool(
        self, user_id: UserId, pool_id: UserId, new_balance: MoneySum
    ) -> bool:
        result = await self.pools_coll.update_one(
            self._pool_filter(user_id, pool_id),
            {"$push": {"pool.balance": new_balance.model_dump(mode="json")}},
        )
        return result.modified_count == 1

    async def _update_pool_internal(
        self,
        user_id: UserId,
        pool: MoneyPool,
        transaction: Transaction,
        session: AsyncIOMotorClientSession | None,
    ):
        new_sum_idx_in_balance, new_sum = pool.update_with_transaction(transaction)
        await self.pools_coll.update_one(
            self._pool_filter(user_id, transaction.pool_id),
            {"$set": {f"pool.balance.{new_sum_idx_in_balance}": new_sum.model_dump(mode="json")}},
            session=session,
        )

    async def add_transaction(
        self, user_id: UserId, transaction: Transaction
    ) -> StoredTransaction:
        async def internal(session: AsyncIOMotorClientSession) -> StoredTransaction:
            pool = await self._load_pool_internal(user_id, transaction.pool_id, session=session)
            if pool is None:
                raise ValueError("Attempt to add transaction to a non-existing pool")
            await self._update_pool_internal(user_id, pool, transaction, session=session)
            result = await self.transactions_coll.insert_one(
                OwnedTransaction(transaction=transaction, owner=user_id).model_dump(mode="json"),
                session=session,
            )
            return StoredTransaction.from_transaction(transaction, id=str(result.inserted_id))

        async with await self.client.start_session() as session:
            return await session.with_transaction(internal)

    async def load_transactions(
        self, user_id: UserId, filter: TransactionFilter | None, offset: int, count: int
    ) -> list[StoredTransaction]:
        docs = (
            await self.transactions_coll.find(
                {"owner": user_id},
                # TODO support filtering
            )
            .sort("transaction.timestamp", -1)
            .skip(offset)
            .to_list(length=count)
        )

        return [OwnedTransaction.model_validate(d).to_stored_transaction() for d in docs]

    def _transaction_filter(
        self, user_id: UserId, transaction_id: TransactionId
    ) -> dict[str, Any]:
        return {
            "_id": ObjectId(transaction_id),
            "owner": user_id,
        }

    async def _load_transaction_internal(
        self, user_id: UserId, transaction_id: TransactionId, session: AsyncIOMotorClientSession
    ) -> OwnedTransaction | None:
        raw = await self.transactions_coll.find_one(
            self._transaction_filter(user_id, transaction_id), session=session
        )
        return OwnedTransaction.model_validate(raw) if raw else None

    async def delete_transaction(self, user_id: UserId, transaction_id: MoneyPoolId) -> bool:
        async def internal(session: AsyncIOMotorClientSession) -> bool:
            to_be_deleted = await self._load_transaction_internal(
                user_id, transaction_id, session=session
            )
            if to_be_deleted is None:
                return False
            result = await self.transactions_coll.delete_one(
                self._transaction_filter(user_id, transaction_id), session=session
            )
            if result.deleted_count == 0:
                return False
            inverse_transaction = copy.deepcopy(to_be_deleted.transaction)
            inverse_transaction.sum.amount = -inverse_transaction.sum.amount

            pool = await self._load_pool_internal(
                user_id, inverse_transaction.pool_id, session=session
            )
            if pool is None:
                return False
            await self._update_pool_internal(user_id, pool, inverse_transaction, session=session)
            return True

        async with await self.client.start_session() as session:
            return await session.with_transaction(internal)
