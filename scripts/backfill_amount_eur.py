import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv

from api import exchange_rates
from api.storage import MongoDbStorage
from api.types.currency import parse_currency
from api.types.money_sum import MoneySum


load_dotenv()


async def main() -> None:
    storage = MongoDbStorage(os.environ["MONGODB_URL"])
    rates = exchange_rates.RemoteExchangeRates(
        api_url=os.environ["EXCHANGE_RATES_API_URL"],
        cache_file_path=Path(__file__).parent.parent / "exchange_rates_cache.json",
    )
    eur = parse_currency("EUR")
    print(eur)

    await rates.initialize()
    transactions_coll = storage.transactions_coll
    counter = 0
    async for td in transactions_coll.find():
        if td["transaction"].get("amount_eur") is not None:
            continue

        sum = MoneySum.model_validate(td["transaction"]["sum"])
        rate = await rates.get_rate(
            base=sum.currency,
            target=eur,
        )
        sum_euro = float(sum.amount) * rate.rate

        await transactions_coll.update_one(
            {"_id": td["_id"]},
            {
                "$set": {
                    "transaction.amount_eur": sum_euro,
                }
            },
        )
        print(f"{counter: >5}: {td['_id']} {sum} -> {sum_euro:.3f} EUR")
        counter += 1


asyncio.run(main())
