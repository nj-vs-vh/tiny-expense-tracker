import datetime
from fastapi.testclient import TestClient


def test_api(client: TestClient) -> None:
    response = client.get("/pools")
    assert response.status_code == 200
    assert response.json() == {}


def test_basic_flow(client: TestClient) -> None:
    response = client.post(
        "/pools",
        json={
            "display_name": "My first pool",
            "balance": [
                {"amount": 0, "currency": "USD"},
                {"amount": 10, "currency": "EUR"},
            ],
        },
    )
    assert response.status_code == 200
    pool_id = response.json()["id"]

    response = client.get(
        f"/pools/{pool_id}",
    )
    assert response.status_code == 200
    assert response.json() == {
        "display_name": "My first pool",
        "balance": [
            {"amount": "0.00", "currency": "USD"},
            {"amount": "10.00", "currency": "EUR"},
        ],
    }

    response = client.post(
        "/transactions",
        json={
            "timestamp": datetime.datetime.now().isoformat(),
            "sum": {"amount": 100, "currency": "USD"},
            "pool_id": pool_id,
            "description": "test",
        },
    )
    assert response.status_code == 200

    response = client.get(
        f"/pools",
    )
    assert response.status_code == 200
    assert response.json() == {
        pool_id: {
            "display_name": "My first pool",
            "balance": [
                {"amount": "100.00", "currency": "USD"},
                {"amount": "10.00", "currency": "EUR"},
            ],
        }
    }


def test_currency_coercion(client: TestClient) -> None:
    response = client.post(
        "/pools",
        json={
            "display_name": "dollars",
            "balance": [
                {"amount": 300, "currency": "USD"},
            ],
        },
    )
    assert response.status_code == 200
    pool_id = response.json()["id"]

    dt = datetime.datetime.now().isoformat()
    response = client.post(
        "/transactions",
        json={
            "timestamp": dt,
            "sum": {"amount": -100, "currency": "AMD"},
            "pool_id": pool_id,
            "description": "payment in Armenian Drams",
        },
    )
    assert response.status_code == 200

    response = client.get(f"/pools")
    assert response.status_code == 200
    assert response.json() == {
        pool_id: {
            "display_name": "dollars",
            "balance": [{"amount": "200.00", "currency": "USD"}],
        }
    }

    response = client.get("/transactions")
    assert response.status_code == 200
    assert response.json() == [
        {
            "timestamp": dt,
            "sum": {
                "amount": "-100.00",
                "currency": "USD",
            },
            "description": "payment in Armenian Drams",
            "is_diffuse": False,
            "pool_id": pool_id,
            "original_currency": "AMD",
        },
    ]
