import copy
import datetime
import uuid
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
            dt_epoch = dt.timestamp()
            now = datetime.datetime.now().timestamp()
            return dt_epoch < now and now - dt_epoch < 60

    return mask_recursively(
        data, predicate=looks_like_recent_timestamp, mask=lambda _: RECENT_TIMESTAMP
    )


MASKED_ID = "<masked id>"


def mask_ids(data: DataT) -> DataT | str:
    def is_dict_with_id(value: Any) -> bool:
        if not isinstance(value, dict):
            return False
        else:
            return "id" in value

    def mask_id_field(value: dict):
        masked = copy.deepcopy(value)
        masked["id"] = MASKED_ID
        return masked

    return mask_recursively(data, predicate=is_dict_with_id, mask=mask_id_field)
