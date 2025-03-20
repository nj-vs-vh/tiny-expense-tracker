import base64

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey, generate_private_key
from fastapi.testclient import TestClient

from api.app import create_app
from api.auth import RSAAuth
from api.exchange_rates import DumbExchangeRates
from api.storage import InmemoryStorage


@pytest.fixture
def client_with_rsa_auth() -> tuple[bytes, TestClient]:
    private_key = generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    private_key_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )

    public_key = private_key.public_key()
    public_key_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    app = create_app(
        storage=InmemoryStorage(),
        auth=RSAAuth(public_keys=[public_key_bytes]),
        exchange_rates=DumbExchangeRates(),
    )
    return private_key_bytes, TestClient(app)


def test_rsa_auth(client_with_rsa_auth: tuple[bytes, TestClient]):
    private_key_bytes, client = client_with_rsa_auth
    private_key = serialization.load_pem_private_key(
        private_key_bytes,
        password=None,
    )
    assert isinstance(private_key, RSAPrivateKey)

    resp = client.get("/pools", headers={"user-id": "hello", "signature": "what?"})
    assert resp.status_code == 403
    assert resp.json() == {"detail": "Invalid signature"}

    user_id = "John Pork"
    signature_bytes = private_key.sign(
        data=user_id.encode("utf-8"),
        padding=padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
        algorithm=hashes.SHA256(),
    )
    signature = base64.b64encode(signature_bytes).decode("utf-8")
    print(signature)

    resp = client.get(
        "/pools",
        headers={
            "user-id": user_id,
            "signature": signature,
        },
    )
    assert resp.status_code == 200
    assert resp.json() == []

    resp = client.get("/pools", headers={"user-id": "Another user", "signature": signature})
    assert resp.status_code == 403
    assert resp.json() == {"detail": "Invalid signature"}
