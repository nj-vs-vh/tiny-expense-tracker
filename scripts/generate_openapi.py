import json
from pathlib import Path

from api.app import create_app
from api.auth import NoAuth
from api.exchange_rates import DumbExchangeRates
from api.storage import InmemoryStorage

ROOT_DIR = Path(__file__).parent.parent
OPENAPI_JSON = ROOT_DIR / "openapi.json"

if __name__ == "__main__":
    app = create_app(
        storage=InmemoryStorage(),
        auth=NoAuth(),
        exchange_rates=DumbExchangeRates(),
    )
    openapi = app.openapi()
    OPENAPI_JSON.write_text(
        json.dumps(
            openapi,
            indent=4,
            sort_keys=False,
        )
    )
