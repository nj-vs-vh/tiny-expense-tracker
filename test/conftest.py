import pytest
from api.app import create_app
from fastapi.testclient import TestClient
from api.auth import NoAuth
from api.storage import InmemoryStorage
from api.exchange_rates import DumbExchangeRates


@pytest.fixture
def client() -> TestClient:
    app = create_app(
        storage=InmemoryStorage(),
        auth=NoAuth(),
        exchange_rates=DumbExchangeRates(),
    )
    return TestClient(app)
