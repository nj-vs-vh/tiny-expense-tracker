from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException
import pydantic

from api.auth import Auth
from api.storage import Storage
from api.types import MoneyPoolIdResponse, UserId
from api.types.money_pool import MoneyPool, MoneyPoolId
from api.types.transaction import Transaction

Offset = Annotated[int, pydantic.Field(ge=0)]
Count = Annotated[int, pydantic.Field(ge=1, le=200)]


def create_app(storage: Storage, auth: Auth) -> FastAPI:
    app = FastAPI()

    AthorizedUser = Annotated[UserId, Depends(auth.authorize_request)]

    @app.post("/pools")
    async def create_pool(
        user_id: AthorizedUser, new_pool: MoneyPool
    ) -> MoneyPoolIdResponse:
        pool_id = await storage.add_pool(user_id=user_id, new_pool=new_pool)
        return {"id": pool_id}

    @app.get("/pools")
    async def get_pools(user_id: AthorizedUser) -> dict[MoneyPoolId, MoneyPool]:
        return await storage.load_pools(user_id=user_id)

    @app.get("/pools/{pool_id}")
    async def get_pools(user_id: AthorizedUser, pool_id: str) -> MoneyPool:
        pool = await storage.load_pool(user_id=user_id, pool_id=pool_id)
        if pool is None:
            raise HTTPException(status_code=404, detail="Pool not found")

    @app.post("/transactions")
    async def add_transaction(user_id: AthorizedUser, transaction: Transaction):
        await storage.add_transaction(user_id=user_id, transaction=transaction)

    @app.get("/transactions")
    async def get_transactions(
        user_id: AthorizedUser, offset: Offset, count: Count
    ) -> list[Transaction]:
        return await storage.load_transactions(
            user_id=user_id, offset=offset, count=count
        )

    return app
