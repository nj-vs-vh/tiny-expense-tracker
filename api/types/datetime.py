import datetime
from typing import Annotated, Any

import pydantic


def parse_datetime(v: Any) -> datetime.datetime:
    if isinstance(v, datetime.datetime):
        return v
    elif isinstance(v, float):
        return datetime.datetime.fromtimestamp(v, tz=datetime.UTC)
    elif isinstance(v, str):
        return datetime.datetime.fromisoformat(v)
    else:
        raise ValueError("expected UNIX timestamp or ISO string")


Datetime = Annotated[
    datetime.datetime,
    pydantic.BeforeValidator(parse_datetime),
    pydantic.PlainSerializer(lambda dt: dt.timestamp(), return_type=float),
    pydantic.WithJsonSchema({"type": "number"}),
]
