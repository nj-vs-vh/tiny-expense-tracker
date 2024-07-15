import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from api.auth import NoAuth
from api.exchange_rates import DumbExchangeRates
from api.storage import InmemoryStorage


@pytest.fixture
def client() -> TestClient:
    app = create_app(
        storage=InmemoryStorage(),
        auth=NoAuth(),
        exchange_rates=DumbExchangeRates(),
    )
    return TestClient(app)
