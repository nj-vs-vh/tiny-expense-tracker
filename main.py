from api.app import create_app
from api.storage import InmemoryStorage

app = create_app(InmemoryStorage())
