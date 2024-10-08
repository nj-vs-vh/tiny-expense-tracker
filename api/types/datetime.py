import datetime as dt
from typing import Annotated, Any

import pydantic


def parse_datetime(v: Any) -> dt.datetime:
    if isinstance(v, dt.datetime):
        return v
    elif isinstance(v, float):
        return dt.datetime.fromtimestamp(v, tz=dt.UTC)
    elif isinstance(v, str):
        try:
            return dt.datetime.fromtimestamp(float(v), tz=dt.UTC)
        except:
            return dt.datetime.fromisoformat(v)
    else:
        raise ValueError("expected UNIX timestamp or ISO string")


Datetime = Annotated[
    dt.datetime,
    pydantic.BeforeValidator(parse_datetime),
    pydantic.PlainSerializer(lambda dt: dt.timestamp(), return_type=float),
    pydantic.WithJsonSchema({"type": "number"}),
]
