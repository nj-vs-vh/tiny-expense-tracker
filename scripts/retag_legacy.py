import asyncio
import datetime
import os
from dotenv import load_dotenv

from api.storage import MongoDbStorage, TransactionOrder
from api.types.api import TransactionUpdate
from api.types.transaction import TransactionFilter


load_dotenv()


async def main() -> None:
    storage = MongoDbStorage(os.environ["MONGODB_URL"])
    user_id = os.environ["USER_ID"]
    period = datetime.timedelta(days=365)
    now = datetime.datetime.now()

    transaction_coll = storage.transactions_coll

    all_tags = []
    async for doc in transaction_coll.aggregate(
        [
            {"$match": {"owner": user_id}},
            {"$sort": {"transaction.timestamp": -1}},
            {"$project": {"tags": "$transaction.tags", "_id": 0}},
            {"$unwind": "$tags"},
            {"$group": {"_id": None, "tags_unique": {"$addToSet": "$tags"}}},
            # {"$limit": 30},
        ]
    ):
        all_tags = doc["tags_unique"]

    print("All tags:")
    print(", ".join(all_tags))

    transactions = await storage.load_transactions(
        user_id,
        filter=TransactionFilter(
            min_timestamp=now - period,
            max_timestamp=now,
            is_diffuse=False,
            untagged_only=True,
        ),
        order=TransactionOrder.LARGEST_NEGATIVE,
        offset=0,
        count=100_000,
    )
    print(f"Got a total of {len(transactions)} transactions")

    for transaction in transactions:
        print(f"{transaction.timestamp} {transaction.sum} {transaction.description}")
        action = input("[tag, s to skip, q to quit] > ")
        if action == "q":
            break
        elif action == "s":
            continue
        elif not action:
            print("No action provided, skipping")
            continue
        print(f"Applying tag {action}")
        await storage.update_transaction(
            user_id,
            transaction_id=transaction.id,
            update=TransactionUpdate(
                tags=[action],
            ),
        )


asyncio.run(main())
