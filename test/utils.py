import datetime
from typing import Any, Callable, TypeVar

from typing_extensions import TypeGuard


DataT = TypeVar("DataT")


def mask_recursively(
    data: DataT,
    predicate: Callable[[Any], bool],
    mask: Callable[[Any], str],
) -> DataT | str:
    if predicate(data):
        return mask(data)
    elif isinstance(data, dict):
        return {k: mask_recursively(v, predicate, mask) for k, v in data.items()}  # type: ignore
    elif isinstance(data, list):
        return [mask_recursively(item, predicate, mask) for item in data]  # type: ignore
    else:
        return data


RECENT_TIMESTAMP = "<recent timestamp>"


def mask_recent_timestamps(data: DataT) -> DataT | str:
    def looks_like_recent_timestamp(value: Any) -> bool:
        if not isinstance(value, (float, str)):
            return False
        converters = (datetime.datetime.fromisoformat, datetime.datetime.fromtimestamp)
        dt: datetime.datetime | None = None
        for converter in converters:
            try:
                dt = converter(value)  # type: ignore
                break
            except Exception:
                pass
        if dt is None:
            return False
        else:
            now = datetime.datetime.now()
            return dt < now and now - dt < datetime.timedelta(minutes=1)

    return mask_recursively(
        data, predicate=looks_like_recent_timestamp, mask=lambda _: RECENT_TIMESTAMP
    )
