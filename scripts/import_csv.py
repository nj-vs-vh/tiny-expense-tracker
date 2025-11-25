import argparse
import asyncio
import csv
import datetime
from decimal import Decimal
import os
import traceback
from typing import Any

from dotenv import load_dotenv

from api.iso4217 import CURRENCIES
from api.storage import MongoDbStorage
from api.types.money_sum import MoneySum
from api.types.transaction import Transaction

load_dotenv()


def parse_transaction(row: dict[str, Any], pool_id: str) -> Transaction:
    date = datetime.date.fromisoformat(row["Date ISO"])
    amount = float(row["Importo €"])
    description = row["Description manual"].strip()
    if description:
        description += " / " + row["Descrizione"]
    else:
        description = row["Descrizione"]
    description += " (imported from CSV)"
    return Transaction(
        sum=MoneySum(amount=Decimal(amount), currency=CURRENCIES["EUR"]),
        pool_id=pool_id,
        description=description,
        timestamp=datetime.datetime.combine(date, time=datetime.time(hour=12)),
        amount_eur=amount,
        is_diffuse=False,
        tags=row["Tags"].split(","),
    )


async def main(file: str, pool_name: str) -> None:
    storage = MongoDbStorage(os.environ["MONGODB_URL"])
    user_id = os.environ["USER_ID"]

    pools = await storage.load_pools(user_id)
    matched = [p for p in pools if p.display_name == pool_name]
    if not matched:
        raise SystemExit(f"Pool not found: {pool_name}")

    pool_id = matched[0].id

    transactions: list[Transaction] = []
    with open(file, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                transactions.append(parse_transaction(row, pool_id=pool_id))
            except Exception:
                print("Error parsing transaction")
                traceback.print_exc()

    print(f"Parsed {len(transactions)} transactions, uploading")

    for i, transaction in enumerate(transactions):
        print(f"{i + 1} / {len(transactions)}")
        await storage.add_transaction(user_id, transaction)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("csv")
    parser.add_argument("--pool-name", required=True)
    args = parser.parse_args()

    asyncio.run(main(args.csv, args.pool_name))
