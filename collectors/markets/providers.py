"""Market data provider implementations (markets.yaml: providers)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

from collectors.base import get_json

FRED_OBSERVATIONS_URL = "https://api.stlouisfed.org/fred/series/observations"
FRANKFURTER_URL = "https://api.frankfurter.dev/v1/latest"
COINBASE_CANDLES_URL = "https://api.exchange.coinbase.com/products/{symbol}/candles"
COINBASE_MAX_CANDLES = 96


@dataclass
class Candle:
    symbol: str
    ts: str
    interval: str
    open: float
    high: float
    low: float
    close: float
    volume: float | None
    provider: str


@dataclass
class MacroValue:
    series_id: str
    date: str
    value: float | None
    name: str = ""
    source: str = "fred"
    country: str = ""


class MarketDataProvider(Protocol):
    name: str

    def fetch(self, provider_symbol: str, canonical: str) -> list[Candle]: ...


def _day_ts(date: str) -> str:
    return f"{date}T00:00:00+00:00"


def parse_frankfurter(data: dict, quote: str, canonical: str) -> list[Candle]:
    rate = data.get("rates", {}).get(quote)
    date = data.get("date", "")
    if rate is None or not date:
        return []
    rate = float(rate)
    return [
        Candle(
            symbol=canonical,
            ts=_day_ts(date),
            interval="1d",
            open=rate,
            high=rate,
            low=rate,
            close=rate,
            volume=None,
            provider="frankfurter",
        )
    ]


def parse_fred_candles(data: dict, canonical: str) -> list[Candle]:
    candles: list[Candle] = []
    for obs in data.get("observations", []):
        raw = obs.get("value", ".")
        if raw in (".", "", None):
            continue
        value = float(raw)
        candles.append(
            Candle(
                symbol=canonical,
                ts=_day_ts(obs["date"]),
                interval="1d",
                open=value,
                high=value,
                low=value,
                close=value,
                volume=None,
                provider="fred",
            )
        )
    candles.sort(key=lambda c: c.ts)
    return candles


def parse_coinbase_candles(data: list, canonical: str) -> list[Candle]:
    rows = sorted(data, key=lambda r: r[0])[-COINBASE_MAX_CANDLES:]
    candles: list[Candle] = []
    for ts, low, high, open_, close, volume in rows:
        candles.append(
            Candle(
                symbol=canonical,
                ts=datetime.fromtimestamp(ts, tz=timezone.utc).isoformat(),
                interval="15m",
                open=float(open_),
                high=float(high),
                low=float(low),
                close=float(close),
                volume=float(volume),
                provider="coinbase",
            )
        )
    return candles


class FrankfurterProvider:
    name = "frankfurter"

    def fetch(self, provider_symbol: str, canonical: str) -> list[Candle]:
        base, quote = provider_symbol.split("/")
        data = get_json(FRANKFURTER_URL, params={"base": base, "symbols": quote})
        return parse_frankfurter(data, quote, canonical)


class FredMarketProvider:
    name = "fred"

    def fetch(self, provider_symbol: str, canonical: str) -> list[Candle]:
        api_key = os.environ.get("FRED_API_KEY")
        if not api_key:
            return []
        data = get_json(
            FRED_OBSERVATIONS_URL,
            params={
                "series_id": provider_symbol,
                "api_key": api_key,
                "file_type": "json",
                "sort_order": "desc",
                "limit": 10,
            },
        )
        return parse_fred_candles(data, canonical)


class CoinbaseProvider:
    name = "coinbase"

    def fetch(self, provider_symbol: str, canonical: str) -> list[Candle]:
        data = get_json(
            COINBASE_CANDLES_URL.format(symbol=provider_symbol),
            params={"granularity": 900},
        )
        return parse_coinbase_candles(data, canonical)
