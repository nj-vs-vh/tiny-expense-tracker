import asyncio
import datetime
import os
from dotenv import load_dotenv

from api.storage import MongoDbStorage
from api.types.api import TransactionUpdate
from api.types.transaction import TransactionFilter


load_dotenv()


async def main() -> None:
    storage = MongoDbStorage(os.environ["MONGODB_URL"])
    user_id = "no-auth"
    tran_id = "669539a8dd07c49de766f7d7"
    res = await storage.load_transactions(
        user_id,
        filter=TransactionFilter(transaction_ids=[tran_id]),
        offset=0,
        count=1,
    )
    assert res
    t = res[0]
    print(t)

    await storage.update_transaction(
        user_id,
        tran_id,
        update=TransactionUpdate(
            description=t.description + " (again)",
            tags=["test", "upd"],
            timestamp=t.timestamp - datetime.timedelta(days=1),
        ),
    )

    print(
        await storage.load_transactions(
            user_id,
            filter=TransactionFilter(transaction_ids=[tran_id]),
            offset=0,
            count=1,
        )
    )


asyncio.run(main())
