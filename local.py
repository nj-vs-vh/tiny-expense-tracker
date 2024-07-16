import logging

from api.app import create_app
from api.auth import TokenAuth
from api.exchange_rates import DumbExchangeRates
from api.storage import InmemoryStorage

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)-10s%(asctime)s %(name)s: %(message)s",
)

app = create_app(
    storage=InmemoryStorage(),
    auth=TokenAuth(server_tokens=["example-token"]),
    exchange_rates=DumbExchangeRates(),
)
