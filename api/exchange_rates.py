import abc
import asyncio
import datetime
import json
import logging
from pathlib import Path
import random
import time
from typing import Literal, TypedDict

import aiohttp
import pydantic

from api.types.currency import Currency
from api.types.money_sum import MoneySum

logger = logging.getLogger(__name__)


class ExchangeRates(abc.ABC):

    @abc.abstractmethod
    async def initialize(self) -> None: ...

    @abc.abstractmethod
    def convert(self, sum_: MoneySum, new_currency: Currency) -> MoneySum: ...


class DumpExchangeRates(ExchangeRates):
    async def initialize(self) -> None:
        pass

    def convert(self, sum_: MoneySum, new_currency: Currency) -> MoneySum:
        return MoneySum(amount=sum_.amount, currency=new_currency)


class ExchangeRatesApiResponse(TypedDict):
    result: Literal["success"] | str
    time_last_update_unix: int
    time_last_update_utc: str
    time_next_update_unix: int
    time_next_update_utc: str
    time_eol_unix: int
    base_code: Literal["USD"]
    rates: dict[str, float]


ExchangeRatesApiResponseValidator = pydantic.TypeAdapter(ExchangeRatesApiResponse)


class RemoteExchangeRates(ExchangeRates):
    def __init__(self, api_url: str, cache_file_path: Path) -> None:
        self.api_url = api_url
        self.cache_file_path = cache_file_path
        self._cached_response: ExchangeRatesApiResponse | None = None

    @property
    def cached_response(self) -> ExchangeRatesApiResponse:
        if self._cached_response is None:
            raise RuntimeError("Exchange rates are not initialized")
        return self._cached_response

    async def load_exchange_rates(self) -> ExchangeRatesApiResponse:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.api_url) as resp:
                    return ExchangeRatesApiResponseValidator.validate_json(
                        await resp.text()
                    )
        except Exception:
            logger.exception(
                "Error calling exchange rates API, will try to use cached file"
            )

        try:
            return ExchangeRatesApiResponseValidator.validate_json(
                self.cache_file_path.read_text()
            )
        except Exception:
            logger.exception("Error reading cached exchange rates from file")

    async def _load_and_cache_exchange_rates(self) -> None:
        self._cached_response = await self.load_exchange_rates()
        self.cache_file_path.write_text(json.dumps(self._cached_response))

    async def _periodic_update(self) -> None:
        while True:
            if self._cached_response is not None:
                sleep_time = (
                    self._cached_response["time_next_update_unix"] - time.time()
                )
                sleep_time = max(sleep_time, 0)
                sleep_time += 60 * random.randint(60, 5 * 60)  # add 1 to 5 hours
            else:
                sleep_time = datetime.timedelta(days=1).total_seconds()
            logger.info(f"Sleeping for: {datetime.timedelta(seconds=sleep_time)}")
            await asyncio.sleep(sleep_time)
            try:
                logger.info("Updating exchange rates...")
                await self._load_and_cache_exchange_rates()
            except Exception:
                logger.info("Failed to update, will try another time", exc_info=True)

    async def initialize(self) -> None:
        await self._load_and_cache_exchange_rates()
        asyncio.create_task(
            self._periodic_update(), name="periodic exchange rates update"
        )
