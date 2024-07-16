import logging
import os
from pathlib import Path

from dotenv import load_dotenv

from api.app import create_app
from api.auth import NoAuth, TokenAuth
from api.exchange_rates import DumbExchangeRates, RemoteExchangeRates
from api.storage import MongoDbStorage

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)-10s%(asctime)s %(name)s: %(message)s",
)
logging.info("TEST")

app = create_app(
    storage=MongoDbStorage(url=os.environ["MONGODB_URL"]),  # type: ignore
    auth=TokenAuth(server_tokens=os.environ["STATIC_TOKENS"].split(",")),
    exchange_rates=RemoteExchangeRates(
        api_url=os.environ["EXCHANGE_RATES_API_URL"],
        cache_file_path=Path(__file__).parent / ".exchange-rates.json",
    ),
)
