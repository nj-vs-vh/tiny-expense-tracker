import datetime
from test.utils import MASKED_ID, RECENT_TIMESTAMP, mask_ids, mask_recent_timestamps

from fastapi.testclient import TestClient


def test_api(client: TestClient) -> None:
    response = client.get("/pools")
    assert response.status_code == 200
    assert response.json() == []


def test_basic_flow(client: TestClient) -> None:
    response = client.post(
        "/pools",
        json={
            "display_name": "My first pool",
            "balance": [
                {"amount": 0, "currency": "USD"},
                {"amount": 10, "currency": "EUR"},
            ],
            "display_color": "red",
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
        "display_color": "red",
        "id": pool_id,
        "is_visible": True,
        "last_updated": None,
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
    assert mask_recent_timestamps(response.json()) == [
        {
            "display_name": "My first pool",
            "balance": [
                {"amount": "100.00", "currency": "USD"},
                {"amount": "10.00", "currency": "EUR"},
            ],
            "display_color": "red",
            "id": pool_id,
            "is_visible": True,
            "last_updated": RECENT_TIMESTAMP,
        }
    ]


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

    dt = datetime.datetime.now()
    response = client.post(
        "/transactions",
        json={
            "timestamp": dt.isoformat(),
            "sum": {"amount": -100, "currency": "AMD"},
            "pool_id": pool_id,
            "description": "payment in Armenian Drams",
        },
    )
    assert response.status_code == 200

    response = client.get(f"/pools")
    assert response.status_code == 200
    assert mask_recent_timestamps(response.json()) == [
        {
            "display_name": "dollars",
            "id": pool_id,
            "balance": [{"amount": "200.00", "currency": "USD"}],
            "display_color": None,
            "is_visible": True,
            "last_updated": RECENT_TIMESTAMP,
        }
    ]

    response = client.get("/transactions")
    assert response.status_code == 200
    assert mask_ids(response.json()) == [
        {
            "timestamp": dt.timestamp(),
            "sum": {
                "amount": "-100.00",
                "currency": "USD",
            },
            "description": "payment in Armenian Drams",
            "is_diffuse": False,
            "pool_id": pool_id,
            "original_currency": "AMD",
            "id": MASKED_ID,
            "tags": [],
        },
    ]


def test_sync_balance(client: TestClient) -> None:
    response = client.post(
        "/pools",
        json={
            "display_name": "my money",
            "balance": [
                {"amount": 300, "currency": "USD"},
                {"amount": 500, "currency": "GEL"},
                {"amount": 50, "currency": "EUR"},
            ],
        },
    )
    assert response.status_code == 200
    pool_id = response.json()["id"]

    response = client.post(
        f"/sync-balance/{pool_id}",
        json={
            "amounts": [290, 490.5, 0],
        },
    )
    assert response.status_code == 200

    response = client.get(f"/pools")
    assert response.status_code == 200
    assert mask_recent_timestamps(response.json()) == [
        {
            "display_name": "my money",
            "id": pool_id,
            "balance": [
                {"amount": "290.00", "currency": "USD"},
                {"amount": "490.50", "currency": "GEL"},
                {"amount": "0.00", "currency": "EUR"},
            ],
            "display_color": None,
            "is_visible": True,
            "last_updated": RECENT_TIMESTAMP,
        }
    ]

    response = client.get("/transactions")
    assert response.status_code == 200
    assert mask_ids(mask_recent_timestamps(response.json())) == [
        {
            "description": "my money synced 300.00 -> 290.00 USD",
            "is_diffuse": True,
            "original_currency": None,
            "pool_id": pool_id,
            "sum": {
                "amount": "-10.00",
                "currency": "USD",
            },
            "timestamp": RECENT_TIMESTAMP,
            "id": MASKED_ID,
            "tags": [],
        },
        {
            "description": "my money synced 500.00 -> 490.50 GEL",
            "is_diffuse": True,
            "original_currency": None,
            "pool_id": pool_id,
            "sum": {
                "amount": "-9.50",
                "currency": "GEL",
            },
            "timestamp": RECENT_TIMESTAMP,
            "id": MASKED_ID,
            "tags": [],
        },
        {
            "description": "my money synced 50.00 -> 0.00 EUR",
            "is_diffuse": True,
            "original_currency": None,
            "pool_id": pool_id,
            "sum": {
                "amount": "-50.00",
                "currency": "EUR",
            },
            "timestamp": RECENT_TIMESTAMP,
            "id": MASKED_ID,
            "tags": [],
        },
    ]


def test_transfer_between_pools(client: TestClient) -> None:
    response = client.post(
        "/pools",
        json={"display_name": "debit card", "balance": [{"amount": 300, "currency": "USD"}]},
    )
    assert response.status_code == 200
    pool1_id = response.json()["id"]

    response = client.post(
        "/pools",
        json={"display_name": "cash", "balance": [{"amount": 0, "currency": "USD"}]},
    )
    assert response.status_code == 200
    pool2_id = response.json()["id"]

    response = client.post(
        "/transfer",
        json={
            "from_pool": pool1_id,
            "to_pool": pool2_id,
            "sum": {"amount": 100, "currency": "USD"},
            "description": "got some cash",
        },
    )
    assert response.status_code == 200
    assert response.text == "OK"

    response = client.get("/pools")
    assert response.status_code == 200
    assert mask_recent_timestamps(response.json()) == [
        {
            "display_name": "debit card",
            "id": pool1_id,
            "balance": [{"amount": "200.00", "currency": "USD"}],
            "display_color": None,
            "is_visible": True,
            "last_updated": RECENT_TIMESTAMP,
        },
        {
            "display_name": "cash",
            "id": pool2_id,
            "balance": [{"amount": "100.00", "currency": "USD"}],
            "display_color": None,
            "is_visible": True,
            "last_updated": RECENT_TIMESTAMP,
        },
    ]

    response = client.get("/transactions")
    assert response.status_code == 200
    assert mask_ids(mask_recent_timestamps(response.json())) == [
        {
            "sum": {"amount": "-100.00", "currency": "USD"},
            "pool_id": pool1_id,
            "description": "Transfer 100.00 USD to cash (got some cash)",
            "timestamp": RECENT_TIMESTAMP,
            "is_diffuse": False,
            "original_currency": None,
            "id": MASKED_ID,
            "tags": [],
        },
        {
            "sum": {"amount": "100.00", "currency": "USD"},
            "pool_id": pool2_id,
            "description": "Transfer 100.00 USD from debit card (got some cash)",
            "timestamp": RECENT_TIMESTAMP,
            "is_diffuse": False,
            "original_currency": None,
            "id": MASKED_ID,
            "tags": [],
        },
    ]


def test_report(client: TestClient) -> None:
    response = client.post(
        "/pools",
        json={"display_name": "debit", "balance": [{"amount": 300, "currency": "USD"}]},
    )
    assert response.status_code == 200
    pool_id = response.json()["id"]

    start = datetime.datetime(year=2024, month=9, day=1, tzinfo=datetime.UTC)
    for amount, days in ((-100, 1), (-50, 5), (-10, 6), (-50, 12), (150, 8)):
        response = client.post(
            "/transactions",
            json={
                "timestamp": (start + datetime.timedelta(days=days)).timestamp(),
                "sum": {"amount": amount, "currency": "USD"},
                "pool_id": pool_id,
                "description": "whatever",
            },
        )
        assert response.status_code == 200

    end = start + datetime.timedelta(days=14)
    response = client.get(
        f"/report",
        params={
            "start": start.isoformat(),
            "end": end.isoformat(),
            "points": 3,
        },
    )
    assert response.status_code == 200
    assert mask_recent_timestamps(response.json()) == {
        "snapshots": [
            {
                "timestamp": end.timestamp(),
                "pool_stats": [
                    {
                        "pool": {
                            "display_name": "debit",
                            "balance": [{"amount": "240.00", "currency": "USD"}],
                            "is_visible": True,
                            "last_updated": RECENT_TIMESTAMP,
                            "display_color": None,
                            "id": pool_id,
                        },
                        "total": {"amount": "240.00", "currency": "EUR"},
                        "fractions": {"USD": 1.0},
                    }
                ],
                "overall_total": {"amount": "240.00", "currency": "EUR"},
            },
            {
                "timestamp": (start.timestamp() + end.timestamp()) / 2,
                "pool_stats": [
                    {
                        "pool": {
                            "display_name": "debit",
                            "balance": [{"amount": "140.00", "currency": "USD"}],
                            "is_visible": True,
                            "last_updated": RECENT_TIMESTAMP,
                            "display_color": None,
                            "id": pool_id,
                        },
                        "total": {"amount": "140.00", "currency": "EUR"},
                        "fractions": {"USD": 1.0},
                    }
                ],
                "overall_total": {"amount": "140.00", "currency": "EUR"},
            },
            {
                "timestamp": start.timestamp(),
                "pool_stats": [
                    {
                        "pool": {
                            "display_name": "debit",
                            "balance": [{"amount": "300.00", "currency": "USD"}],
                            "is_visible": True,
                            "last_updated": RECENT_TIMESTAMP,
                            "display_color": None,
                            "id": pool_id,
                        },
                        "total": {"amount": "300.00", "currency": "EUR"},
                        "fractions": {"USD": 1.0},
                    }
                ],
                "overall_total": {"amount": "300.00", "currency": "EUR"},
            },
        ],
        "spent": {"amount": "210.00", "currency": "EUR"},
        "made": {"amount": "150.00", "currency": "EUR"},
        "tag_totals": [
            {
                "total": {
                    "amount": "-60.00",
                    "currency": "EUR",
                },
                "tag": None,
            },
        ],
    }


def test_net_per_tag(client: TestClient) -> None:
    response = client.post(
        "/pools",
        json={"display_name": "example", "balance": [{"amount": 300, "currency": "USD"}]},
    )
    assert response.status_code == 200
    pool_id = response.json()["id"]

    start = datetime.datetime(year=2024, month=9, day=1, tzinfo=datetime.UTC)

    def make_transaction(amount: float, days: int, tags: list[str]):
        response = client.post(
            "/transactions",
            json={
                "timestamp": (start + datetime.timedelta(days=days)).timestamp(),
                "sum": {"amount": amount, "currency": "USD"},
                "pool_id": pool_id,
                "description": "whatever",
                "tags": tags,
            },
        )
        assert response.status_code == 200

    make_transaction(-10, 1, ["test"])
    make_transaction(-20, 2, ["test"])
    make_transaction(-15, 3, ["another"])
    make_transaction(-100, 4, [])

    response = client.get(
        f"/report",
        params={
            "start": start.isoformat(),
            "points": 2,
        },
    )
    assert response.status_code == 200
    assert mask_recent_timestamps(response.json()) == {
        "snapshots": [
            {
                "timestamp": RECENT_TIMESTAMP,
                "pool_stats": [
                    {
                        "pool": {
                            "display_name": "example",
                            "balance": [{"amount": "155.00", "currency": "USD"}],
                            "is_visible": True,
                            "last_updated": RECENT_TIMESTAMP,
                            "display_color": None,
                            "id": pool_id,
                        },
                        "total": {"amount": "155.00", "currency": "EUR"},
                        "fractions": {"USD": 1.0},
                    }
                ],
                "overall_total": {"amount": "155.00", "currency": "EUR"},
            },
            {
                "timestamp": start.timestamp(),
                "pool_stats": [
                    {
                        "pool": {
                            "display_name": "example",
                            "balance": [{"amount": "300.00", "currency": "USD"}],
                            "is_visible": True,
                            "last_updated": RECENT_TIMESTAMP,
                            "display_color": None,
                            "id": pool_id,
                        },
                        "total": {"amount": "300.00", "currency": "EUR"},
                        "fractions": {"USD": 1.0},
                    }
                ],
                "overall_total": {"amount": "300.00", "currency": "EUR"},
            },
        ],
        "spent": {"amount": "145.00", "currency": "EUR"},
        "made": {"amount": "0.00", "currency": "EUR"},
        "tag_totals": [
            {
                "tag": None,
                "total": {
                    "amount": "-100.00",
                    "currency": "EUR",
                },
            },
            {
                "tag": "test",
                "total": {
                    "amount": "-30.00",
                    "currency": "EUR",
                },
            },
            {
                "tag": "another",
                "total": {
                    "amount": "-15.00",
                    "currency": "EUR",
                },
            },
        ],
    }
