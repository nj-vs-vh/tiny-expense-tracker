import abc
import base64
import logging
from typing import Annotated

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from fastapi import Header, HTTPException

from api.types.ids import UserId

logger = logging.getLogger(__name__)


class Auth(abc.ABC):
    @abc.abstractmethod
    async def authorize_request(self, *args, **kwargs) -> UserId: ...


class NoAuth(Auth):
    async def authorize_request(self) -> UserId:
        return "no-auth"


class DumbSecretHeaderAuth(Auth):
    async def authorize_request(self, secret: Annotated[str | None, Header()]) -> UserId:
        if secret == "secret":
            return "secret-header-auth"
        else:
            raise HTTPException(status_code=403, detail="Missing or invalid auth header")


class RSAAuth(Auth):
    def __init__(self, public_keys: list[bytes]) -> None:
        loaded_keys = [load_pem_public_key(k) for k in public_keys]
        if not all(isinstance(k, RSAPublicKey) for k in loaded_keys):
            raise ValueError("All public keys must be RSA")
        self.public_keys: list[RSAPublicKey] = loaded_keys  # type: ignore

    async def authorize_request(
        self,
        user_id: Annotated[str, Header()],
        signature: Annotated[str, Header(title="Base64-encoded RSA signature for user id")],
    ) -> UserId:
        try:
            signature_bytes = base64.b64decode(signature)
        except Exception:
            raise HTTPException(
                400,
                detail="Signature header must contain base64-encoded signature",
            )
        message = user_id.encode("utf-8")
        for public_key in self.public_keys:
            try:
                public_key.verify(
                    signature=signature_bytes,
                    data=message,
                    padding=padding.PSS(
                        mgf=padding.MGF1(hashes.SHA256()),
                        salt_length=padding.PSS.MAX_LENGTH,
                    ),
                    algorithm=hashes.SHA256(),
                )
                return user_id
            except InvalidSignature:
                pass
        raise HTTPException(403, detail="Invalid signature")


class TokenAuth(Auth):
    def __init__(self, server_tokens: list[str]) -> None:
        self.server_tokens = server_tokens

    async def authorize_request(
        self, user_id: Annotated[str, Header()], token: Annotated[str, Header()]
    ) -> UserId:
        if any(token == server_token for server_token in self.server_tokens):
            # TODO: client token auth
            logger.info(f"Authorized through server token: {user_id!r}")
            return user_id
        else:
            raise HTTPException(403, detail="Invalid token")
