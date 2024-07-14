from api.app import create_app
from api.auth import DumbSecretHeaderAuth
from api.storage import InmemoryStorage

app = create_app(
    storage=InmemoryStorage(),
    auth=DumbSecretHeaderAuth(),
)
