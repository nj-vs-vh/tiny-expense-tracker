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

app = create_app(
    storage=MongoDbStorage(url=os.environ["MONGODB_URL"]),
    # auth=TokenAuth(
    #     server_tokens=["example-token"],
    #     auth_telegram_bot_token=os.environ["AUTH_TGBOT_TOKEN"],
    # ),
    auth=NoAuth(),
    exchange_rates=DumbExchangeRates(),
    frontend_origins=["http://127.0.0.1:5500"],
)
