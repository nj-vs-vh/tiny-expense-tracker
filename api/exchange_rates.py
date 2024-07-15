import abc
import asyncio
import datetime
import json
from locale import currency
import logging
import random
import time
from pathlib import Path
from typing import Literal, TypedDict

import aiohttp
import pydantic

from api.types.currency import Currency, CurrencyAdapter
from api.types.datetime import Datetime

logger = logging.getLogger(__name__)


class ExchangeRate(pydantic.BaseModel):
    base: Currency
    target: Currency
    rate: float
    updated_on: Datetime


class ExchangeRates(abc.ABC):

    async def initialize(self) -> None:
        pass

    @abc.abstractmethod
    async def get_rate(self, base: Currency, target: Currency) -> ExchangeRate: ...


class DumbExchangeRates(ExchangeRates):
    async def get_rate(self, base: Currency, target: Currency) -> ExchangeRate:
        return ExchangeRate(
            base=base,
            target=target,
            rate=1.0,
            updated_on=datetime.datetime.now(),
        )


class ExchangeRatesApiResponse(TypedDict):
    result: str
    time_last_update_unix: int
    time_last_update_utc: str
    time_next_update_unix: int
    time_next_update_utc: str
    time_eol_unix: int
    base_code: str
    rates: dict[str, float]


ExchangeRatesApiResponseValidator = pydantic.TypeAdapter(ExchangeRatesApiResponse)
ExchangeRateList = pydantic.TypeAdapter(list[ExchangeRate])


class RemoteExchangeRates(ExchangeRates):
    def __init__(self, api_url: str, cache_file_path: Path) -> None:
        self.api_url = api_url
        self.cache_file_path = cache_file_path
        self._cached_rates = (
            ExchangeRateList.validate_json(self.cache_file_path.read_text())
            if self.cache_file_path.exists()
            else []
        )

    async def update_exchange_rates(self, base: Currency) -> list[ExchangeRate] | None:
        logger.info(f"Updating exchange rates from {base}")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.api_url + "/" + base.code.upper()) as resp:
                    logger.info(f"Got response from API: {resp}")
                    response = ExchangeRatesApiResponseValidator.validate_json(await resp.text())
                    assert response["result"] == "success"
                    base_retrieved = CurrencyAdapter.validate_python(response["base_code"])
                    new_rates: list[ExchangeRate] = []
                    for target_code, rate in response["rates"].items():
                        try:
                            new_rates.append(
                                ExchangeRate(
                                    base=base_retrieved,
                                    target=CurrencyAdapter.validate_python(target_code),
                                    rate=rate,
                                    updated_on=datetime.datetime.fromtimestamp(
                                        response["time_last_update_unix"]
                                    ),
                                )
                            )
                        except Exception:
                            logger.info(
                                f"Failed to parse exchange rate {base_retrieved} -> {target_code} ({rate})"
                            )
                    logger.info(f"Extracted {len(new_rates)} new rates")
                    merged_rates = self._cached_rates + new_rates
                    merged_rates.sort(key=lambda er: er.updated_on, reverse=True)
                    filtered_rates: list[ExchangeRate] = []
                    seen_pairs: set[tuple[Currency, Currency]] = set()
                    for rate in merged_rates:
                        pair = (rate.base, rate.target)
                        if pair in seen_pairs:
                            continue
                        else:
                            seen_pairs.add(pair)
                            filtered_rates.append(rate)
                    self._cached_rates = filtered_rates
                    logger.exception(f"Cached rates updated, saving on disk")
                    self.cache_file_path.write_bytes(
                        ExchangeRateList.dump_json(self._cached_rates)
                    )
                    logger.exception(f"Cached rates saved to file")
        except Exception:
            logger.exception(f"Error updating exchnage rates for {base}")

    def get_cached_rate_matches(self, base: Currency, target: Currency) -> list[ExchangeRate]:
        return sorted(
            [r for r in self._cached_rates if r.base == base and r.target == target],
            key=lambda er: er.updated_on,
            reverse=True,
        )

    async def get_rate(self, base: Currency, target: Currency) -> ExchangeRate:
        matches = self.get_cached_rate_matches(base, target)
        if not matches or (datetime.datetime.now() - matches[0].updated_on) > datetime.timedelta(
            days=3
        ):
            await self.update_exchange_rates(base)
            matches = self.get_cached_rate_matches(base, target)
            if not matches:
                raise RuntimeError(f"Failed to fetch exchange rate for {base} -> {target}")
        return matches[0]
