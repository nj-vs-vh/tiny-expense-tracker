from datetime import datetime
from typing import Annotated, Any

import pydantic


def parse_datetime(v: Any) -> datetime:
    if isinstance(v, datetime):
        return v
    elif isinstance(v, float):
        return datetime.fromtimestamp(v)
    elif isinstance(v, str):
        return datetime.fromisoformat(v)
    else:
        raise ValueError("expected UNIX timestamp or ISO string")


Datetime = Annotated[
    datetime,
    pydantic.BeforeValidator(parse_datetime),
    pydantic.PlainSerializer(lambda dt: dt.timestamp(), return_type=float),
    pydantic.WithJsonSchema({"type": "number"}),
]
