import logging
import os

from dotenv import load_dotenv

from api.app import create_app
from api.auth import TokenAuth
from api.exchange_rates import DumbExchangeRates
from api.storage import InmemoryStorage

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)-10s%(asctime)s %(name)s: %(message)s",
)

app = create_app(
    storage=InmemoryStorage(),
    auth=TokenAuth(
        server_tokens=["example-token"],
        auth_telegram_bot_token=os.environ["AUTH_TGBOT_TOKEN"],
    ),
    exchange_rates=DumbExchangeRates(),
    frontend_origins=["http://127.0.0.1:5500"],
)
