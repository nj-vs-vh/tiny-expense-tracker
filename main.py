import logging
import os

from dotenv import load_dotenv

from api.app import create_app
from api.auth import NoAuth
from api.exchange_rates import DumbExchangeRates
from api.storage import MongoDbStorage

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)-10s%(asctime)s %(name)s: %(message)s",
)
logging.info("TEST")

app = create_app(
    storage=MongoDbStorage(url=os.environ["MONGODB_URL"]),  # type: ignore
    auth=NoAuth(),
    exchange_rates=DumbExchangeRates(),
)
