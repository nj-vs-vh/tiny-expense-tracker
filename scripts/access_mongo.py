import asyncio
import datetime
import os
from dotenv import load_dotenv

from api.storage import MongoDbStorage, TransactionOrder
from api.types.transaction import TransactionFilter


load_dotenv()


async def main() -> None:
    storage = MongoDbStorage(os.environ["MONGODB_URL"])
    user_id = os.environ["USER_ID"]
    transactions = await storage.load_transactions(
        user_id,
        filter=TransactionFilter(
            min_timestamp=datetime.datetime(2024, 11, 1),
            max_timestamp=datetime.datetime(2024, 11, 30),
            is_diffuse=None,
            untagged_only=True,
        ),
        order=TransactionOrder.OLDEST,
        offset=0,
        count=300,
    )
    print(*transactions, sep="\n\n")


asyncio.run(main())
