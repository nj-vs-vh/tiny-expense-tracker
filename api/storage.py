import abc
import copy
import enum
import logging
import time
import uuid
from typing import Annotated, Any

import fastapi
import pydantic
from bson import ObjectId
from motor.motor_asyncio import (
    AsyncIOMotorClient,
    AsyncIOMotorClientSession,
    AsyncIOMotorCollection,
)

from api.types.api import MoneyPoolAttributesUpdate, TransactionUpdate
from api.types.ids import MoneyPoolId, TransactionId, UserId
from api.types.money_pool import MoneyPool, StoredMoneyPool
from api.types.money_sum import MoneySum
from api.types.transaction import StoredTransaction, Transaction, TransactionFilter


class TransactionOrder(enum.Enum):
    LATEST = "latest"
    OLDEST = "oldest"
    LARGEST = "largest"
    LARGEST_NEGATIVE = "largest_negative"

    def key(self, tran: StoredTransaction) -> float:
        match self:
            case TransactionOrder.LATEST:
                return tran.timestamp.timestamp()
            case TransactionOrder.OLDEST:
                return -tran.timestamp.timestamp()
            case TransactionOrder.LARGEST:
                return -float(tran.sum.amount)
            case TransactionOrder.LARGEST_NEGATIVE:
                return float(tran.sum.amount)


class Storage(abc.ABC):
    async def initialize(self) -> None:
        pass

    @abc.abstractmethod
    async def add_pool(self, user_id: UserId, new_pool: MoneyPool) -> StoredMoneyPool: ...

    @abc.abstractmethod
    async def add_balance_to_pool(
        self, user_id: UserId, pool_id: MoneyPoolId, new_balance: MoneySum
    ) -> bool: ...

    @abc.abstractmethod
    async def set_pool_attributes(
        self, user_id: UserId, pool_id: MoneyPoolId, update: MoneyPoolAttributesUpdate
    ) -> bool: ...

    @abc.abstractmethod
    async def load_pools(self, user_id: UserId) -> list[StoredMoneyPool]: ...

    @abc.abstractmethod
    async def load_pool(self, user_id: UserId, pool_id: MoneyPoolId) -> StoredMoneyPool | None: ...

    @abc.abstractmethod
    async def add_transaction(
        self, user_id: str, transaction: Transaction
    ) -> StoredTransaction: ...

    @abc.abstractmethod
    async def load_transactions(
        self,
        user_id: UserId,
        filter: TransactionFilter | None,
        order: TransactionOrder,
        offset: int,
        count: int,
    ) -> list[StoredTransaction]: ...

    @abc.abstractmethod
    async def delete_transaction(self, user_id: UserId, transaction_id: TransactionId) -> bool: ...

    @abc.abstractmethod
    async def update_transaction(
        self, user_id: UserId, transaction_id: TransactionId, update: TransactionUpdate
    ) -> bool: ...


class InmemoryStorage(Storage):
    """Lacks synchronization, only for testing purposes"""

    def __init__(self) -> None:
        self._user_transactions: dict[UserId, list[StoredTransaction]] = {}
        self._user_pools: dict[UserId, list[StoredMoneyPool]] = {}

    async def add_pool(self, user_id: UserId, new_pool: MoneyPool) -> StoredMoneyPool:
        stored_pool = StoredMoneyPool.from_money_pool(new_pool, id=str(uuid.uuid4()))
        self._user_pools.setdefault(user_id, []).append(stored_pool)
        return copy.deepcopy(stored_pool)

    async def add_balance_to_pool(
        self, user_id: UserId, pool_id: UserId, new_balance: MoneySum
    ) -> bool:
        p = await self._load_pool_internal(user_id, pool_id)
        if p is None:
            return False
        if new_balance.currency not in [s.currency for s in p.balance]:
            p.balance.append(new_balance)
            return True
        else:
            raise ValueError(f"Balance already has currency {new_balance.currency.code}")

    async def set_pool_attributes(
        self, user_id: UserId, pool_id: MoneyPoolId, update: MoneyPoolAttributesUpdate
    ) -> bool:
        p = await self._load_pool_internal(user_id, pool_id)
        if p is None:
            return False
        p.is_visible = update.is_visible or p.is_visible
        p.display_name = update.display_name or p.display_name
        p.display_color = update.display_color or p.display_color
        return True

    async def _load_pools_internal(self, user_id: UserId) -> list[StoredMoneyPool]:
        return self._user_pools.get(user_id, [])

    async def load_pools(self, user_id: UserId) -> list[StoredMoneyPool]:
        return copy.deepcopy(await self._load_pools_internal(user_id))

    async def _load_pool_internal(
        self, user_id: UserId, pool_id: MoneyPoolId
    ) -> StoredMoneyPool | None:
        user_pools = {p.id: p for p in await self._load_pools_internal(user_id)}
        return user_pools.get(pool_id)

    async def load_pool(self, user_id: UserId, pool_id: MoneyPoolId) -> StoredMoneyPool | None:
        return copy.deepcopy(await self._load_pool_internal(user_id, pool_id))

    async def add_transaction(self, user_id: str, transaction: Transaction) -> StoredTransaction:
        pool = await self._load_pool_internal(user_id, transaction.pool_id)
        if pool is None:
            raise ValueError("Transaction attributed to non-existent pool")
        pool.update_with_transaction(transaction)
        stored = StoredTransaction.from_transaction(transaction, id=str(uuid.uuid4()))
        self._user_transactions.setdefault(user_id, []).append(stored)
        self._user_transactions[user_id].sort(key=lambda t: t.timestamp)
        return copy.deepcopy(stored)

    async def load_transactions(
        self,
        user_id: UserId,
        filter: TransactionFilter | None,
        order: TransactionOrder,
        offset: int,
        count: int,
    ) -> list[StoredTransaction]:
        transactions = self._user_transactions.get(user_id, [])
        if filter is not None:
            transactions = [t for t in transactions if filter.matches(t)]
        transactions.sort(key=order.key, reverse=True)  # reverse True to get "most fitting" last
        end = len(transactions) - offset
        start = end - count - 1
        return copy.deepcopy(transactions[start:end])

    def _lookup_transaction(
        self, user_id: UserId, transaction_id: TransactionId
    ) -> tuple[int, StoredTransaction] | None:
        user_transactions = self._user_transactions.get(user_id, [])
        matching_transactions = [
            (i, t) for i, t in enumerate(user_transactions) if t.id == transaction_id
        ]
        if not matching_transactions:
            return None
        return matching_transactions[0]

    async def delete_transaction(self, user_id: UserId, transaction_id: TransactionId) -> bool:
        res = self._lookup_transaction(user_id, transaction_id)
        if res is None:
            return False
        deleted_idx, deleted = res
        deleted = copy.deepcopy(deleted)
        deleted.sum.amount = -deleted.sum.amount  # invert for pool updating purpose
        pool = await self._load_pool_internal(user_id, deleted.pool_id)
        assert pool is not None
        pool.update_with_transaction(deleted)
        self._user_transactions[user_id].pop(deleted_idx)
        return True

    async def update_transaction(
        self, user_id: UserId, transaction_id: TransactionId, update: TransactionUpdate
    ) -> bool:
        res = self._lookup_transaction(user_id, transaction_id)
        if res is None:
            return False
        modified_idx, modified = res
        modified = copy.deepcopy(modified)
        update.apply(modified)
        self._user_transactions[user_id][modified_idx] = modified
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

    def to_stored(self) -> StoredMoneyPool:
        if self.id is None:
            raise ValueError(
                "Attempt to convert non-stored OwnedTransaction (no id attr) to StoredTransaction"
            )
        return StoredMoneyPool.from_money_pool(self.pool, id=self.id)


class OwnedTransaction(MongoStoredModel):
    transaction: Transaction
    owner: UserId

    def to_stored(self) -> StoredTransaction:
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

    async def add_pool(self, user_id: UserId, new_pool: MoneyPool) -> StoredMoneyPool:
        result = await self.pools_coll.insert_one(
            OwnedPool(pool=new_pool, owner=user_id).model_dump(mode="json")
        )
        return StoredMoneyPool.from_money_pool(new_pool, id=str(result.inserted_id))

    def _pool_filter(self, user_id: UserId, pool_id: MoneyPoolId) -> dict[str, Any]:
        if not ObjectId.is_valid(pool_id):
            # HACK: storage is not supposed to validate data in API, but I'm lazy now
            raise fastapi.HTTPException(404, "Invalid pool id")
        return {"_id": ObjectId(pool_id), "owner": user_id}

    async def _load_pool_internal(
        self, user_id: UserId, pool_id: MoneyPoolId, session: AsyncIOMotorClientSession | None
    ) -> StoredMoneyPool | None:
        doc = await self.pools_coll.find_one(self._pool_filter(user_id, pool_id), session=session)
        if doc is None:
            return None
        return OwnedPool.model_validate(doc).to_stored()

    async def load_pool(self, user_id: UserId, pool_id: UserId) -> StoredMoneyPool | None:
        return await self._load_pool_internal(user_id, pool_id, session=None)

    async def load_pools(self, user_id: UserId) -> list[StoredMoneyPool]:
        cursor = self.pools_coll.find({"owner": user_id})
        docs = await cursor.to_list(length=1000)
        return [OwnedPool.model_validate(d).to_stored() for d in docs]

    async def add_balance_to_pool(
        self, user_id: UserId, pool_id: UserId, new_balance: MoneySum
    ) -> bool:
        result = await self.pools_coll.update_one(
            self._pool_filter(user_id, pool_id),
            {"$push": {"pool.balance": new_balance.model_dump(mode="json")}},
        )
        return result.modified_count == 1

    async def set_pool_attributes(
        self, user_id: UserId, pool_id: MoneyPoolId, update: MoneyPoolAttributesUpdate
    ) -> bool:
        result = await self.pools_coll.update_one(
            self._pool_filter(user_id, pool_id),
            {
                "$set": {
                    path: new_value
                    for path, new_value in (
                        ("pool.is_visible", update.is_visible),
                        ("pool.display_name", update.display_name),
                        ("pool.display_color", update.display_color),
                    )
                    if new_value is not None
                }
            },
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
        mongo_set: dict[str, Any] = {
            f"pool.balance.{new_sum_idx_in_balance}": new_sum.model_dump(mode="json"),
        }
        if pool.last_updated is not None:
            mongo_set["pool.last_updated"] = pool.last_updated.isoformat()
        await self.pools_coll.update_one(
            self._pool_filter(user_id, transaction.pool_id), {"$set": mongo_set}, session=session
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
        self,
        user_id: UserId,
        filter: TransactionFilter | None,
        order: TransactionOrder,
        offset: int,
        count: int,
    ) -> list[StoredTransaction]:
        query: dict[str, Any] = {"owner": user_id}
        if filter is not None:
            timestamp_query = {}
            if filter.min_timestamp:
                timestamp_query["$gt"] = filter.min_timestamp.timestamp()
            if filter.max_timestamp:
                timestamp_query["$lt"] = filter.max_timestamp.timestamp()
            if timestamp_query:
                query["transaction.timestamp"] = timestamp_query
            if filter.pool_ids:
                query["transaction.pool_id"] = {"$in": filter.pool_ids}
            if filter.transaction_ids:
                query["_id"] = {"$in": [ObjectId(tid) for tid in filter.transaction_ids]}
            if filter.untagged_only:
                query["transaction.tags"] = {"$size": 0}
                # add for legacy?
                # query["transaction.tags"] = {"$exists": False}
            if filter.is_diffuse is not None:
                query["transaction.is_diffuse"] = filter.is_diffuse

        match order:
            case TransactionOrder.LATEST:
                sort_key, sort_dir = "transaction.timestamp", -1
            case TransactionOrder.OLDEST:
                sort_key, sort_dir = "transaction.timestamp", 1
            case TransactionOrder.LARGEST:
                sort_key, sort_dir = "transaction.amount_eur", -1
            case TransactionOrder.LARGEST_NEGATIVE:
                sort_key, sort_dir = "transaction.amount_eur", 1

        docs = (
            await self.transactions_coll.find(query)
            .sort(sort_key, sort_dir)
            .skip(offset)
            .to_list(length=count)
        )

        return [OwnedTransaction.model_validate(d).to_stored() for d in docs]

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
            inverse_transaction = to_be_deleted.transaction.inverted()
            pool = await self._load_pool_internal(
                user_id, inverse_transaction.pool_id, session=session
            )
            if pool is None:
                return False
            await self._update_pool_internal(user_id, pool, inverse_transaction, session=session)
            return True

        async with await self.client.start_session() as session:
            return await session.with_transaction(internal)

    async def update_transaction(
        self, user_id: UserId, transaction_id: TransactionId, update: TransactionUpdate
    ) -> bool:
        update_doc: dict[str, Any] = {}
        if update.description is not None:
            update_doc["transaction.description"] = update.description
        if update.timestamp is not None:
            update_doc["transaction.timestamp"] = update.timestamp.timestamp()
        if update.tags is not None:
            update_doc["transaction.tags"] = update.tags
        res = await self.transactions_coll.update_one(
            filter=self._transaction_filter(user_id, transaction_id),
            update={"$set": update_doc},
        )
        return res.modified_count == 1
