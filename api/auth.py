import abc
from typing import Annotated

from fastapi import HTTPException, Header

from api.types import UserId


class Auth(abc.ABC):
    @abc.abstractmethod
    async def authorize_request(self, *args, **kwargs) -> UserId: ...


class NoAuth(Auth):
    async def authorize_request(self) -> UserId:
        return "no-auth"


class DumbSecretHeaderAuth(Auth):
    async def authorize_request(
        self, secret: Annotated[str | None, Header()]
    ) -> UserId:
        if secret == "secret":
            return "secret-header-auth"
        else:
            raise HTTPException(
                status_code=403, detail="Missing or invalid auth header"
            )
