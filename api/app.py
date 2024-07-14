from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException

from api.storage import Storage
from api.types import UserId
from api.types.money_pool import MoneyPool


async def auth(secret: Annotated[str | None, Header()] = None) -> UserId:
    if secret == "secret":
        return 123
    else:
        raise HTTPException(status_code=403, detail="Missing or invalid auth header")


AthorizedUser = Annotated[UserId, Depends(auth)]


def create_app(storage: Storage) -> FastAPI:
    app = FastAPI()

    @app.post("/pools")
    async def create_pool(user_id: AthorizedUser, new_pool: MoneyPool):
        pool_id = await storage.add_pool(user_id=user_id, new_pool=new_pool)
        return {"id": pool_id}

    return app
