from api.app import create_app
from fastapi.testclient import TestClient
from api.storage import InmemoryStorage


def test_api(client: TestClient) -> None:
    response = client.get("/pools")
    assert response.status_code == 200
    assert response.json() == {}
