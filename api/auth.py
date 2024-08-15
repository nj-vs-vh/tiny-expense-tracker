import abc
import asyncio
import base64
import logging
import secrets
from hashlib import md5
from typing import Annotated, MutableMapping

import fastapi
from cachetools import TTLCache  # type: ignore
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from fastapi import Header, HTTPException
from fastapi.responses import PlainTextResponse
from telebot import AsyncTeleBot
from telebot import types as tg

from api.types.api import LoginLinkResponse
from api.types.ids import UserId

logger = logging.getLogger(__name__)


class Auth(abc.ABC):
    @abc.abstractmethod
    async def authorize_request(self, *args, **kwargs) -> UserId: ...

    async def initialize(self) -> None:
        pass

    def setup_login_routes(self, app: fastapi.FastAPI) -> None:
        pass


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
    def __init__(self, server_tokens: list[str], auth_telegram_bot_token: str) -> None:
        self.server_tokens = server_tokens
        self.bot = AsyncTeleBot(token=auth_telegram_bot_token)
        self._bot_user: tg.User | None = None
        # NOTE: inmemory storage for simplicity, doesn't support horizontal scaling
        self._access_token_by_bot_start_param: MutableMapping[str, str] = TTLCache(
            maxsize=4096, ttl=5 * 60
        )
        self._user_id_future_by_access_token: MutableMapping[str, asyncio.Future[str]] = dict()

    @property
    def bot_user(self) -> tg.User:
        if self._bot_user is None:
            raise RuntimeError("Attempt to get bot user before initialization")
        return self._bot_user

    async def _get_user_id(self, token: str, timeout_sec: float | None) -> str | None:
        f = self._user_id_future_by_access_token.get(token)
        if f is None:
            raise RuntimeError("Invalid state: no user id future for an access token")
        try:
            return await asyncio.wait_for(f, timeout=timeout_sec or 0.0)
        except asyncio.TimeoutError:
            return None

    async def initialize(self) -> None:
        self._bot_user = await self.bot.get_me()
        logger.info(f"Initialized bot user: {self.bot_user}")

        @self.bot.message_handler(commands=["start"])
        async def login(message: tg.Message):
            message_text_parts = message.text_content.split()
            if len(message_text_parts) <= 1:
                return
            access_token = self._access_token_by_bot_start_param.get(message_text_parts[1])
            if access_token is None:
                return
            user_id_fut = self._user_id_future_by_access_token.get(access_token)
            if user_id_fut is None or user_id_fut.done():
                return
            user_id_fut.set_result(md5(str(message.from_user.id).encode("utf-8")).hexdigest())
            await self.bot.reply_to(message, text="OK")

        asyncio.create_task(self.bot.infinity_polling())

    def setup_login_routes(self, app: fastapi.FastAPI) -> None:
        @app.get("/auth/login-link")
        async def request_login_link() -> LoginLinkResponse:
            start_param = secrets.token_urlsafe(nbytes=16)
            access_token = secrets.token_urlsafe(nbytes=64)
            self._access_token_by_bot_start_param[start_param] = access_token
            self._user_id_future_by_access_token[access_token] = asyncio.Future()
            return LoginLinkResponse(
                url=f"https://t.me/{self.bot_user.username}?start={start_param}",
                start_param=start_param,
            )

        @app.get("/auth/access-token", response_class=PlainTextResponse)
        async def get_access_token_after_login_to_bot(start_param: str) -> str:
            access_token = self._access_token_by_bot_start_param.get(start_param)
            if access_token is None:
                raise HTTPException(404, "Expired or non-existent bot start param")
            timeout = 5 * 60
            user_id = await self._get_user_id(access_token, timeout_sec=timeout)
            if user_id is None:
                raise HTTPException(
                    202, detail=f"User has not logged in through bot after {timeout} sec"
                )
            else:
                return access_token

    async def authorize_request(
        self, token: Annotated[str, Header()], user_id: Annotated[str | None, Header()] = None
    ) -> UserId:
        if any(token == server_token for server_token in self.server_tokens):
            if user_id is None:
                raise HTTPException(400, detail="Valid server token supplied, but no user id")
            logger.info(f"Authorized through server token: {user_id!r}")
            return user_id
        elif user_id := await self._get_user_id(token, timeout_sec=None):
            return user_id
        else:
            raise HTTPException(403, detail="Invalid token")
