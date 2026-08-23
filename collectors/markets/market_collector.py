"""Market price collector (markets.yaml 全体を config として受ける)."""
from __future__ import annotations

from collectors.base import RunStats, logger
from collectors.markets.providers import (
    Candle,
    CoinbaseProvider,
    FrankfurterProvider,
    FredMarketProvider,
    MarketDataProvider,
)

COLLECTOR = "markets"

PROVIDERS: dict[str, MarketDataProvider] = {
    "frankfurter": FrankfurterProvider(),
    "fred": FredMarketProvider(),
    "coinbase": CoinbaseProvider(),
}


def enabled_symbols(config: dict) -> list[dict]:
    return [
        s
        for s in config.get("symbols", [])
        if s.get("enabled") is not False and s.get("providers")
    ]


def collect(config: dict) -> tuple[list[Candle], RunStats]:
    stats = RunStats(collector=COLLECTOR)
    candles: list[Candle] = []
    for symbol in enabled_symbols(config):
        canonical = symbol["canonical"]
        for provider_name, provider_symbol in symbol["providers"].items():
            provider = PROVIDERS.get(provider_name)
            if provider is None:
                stats.failed += 1
                logger.warning(
                    "markets: unknown provider %r for %s", provider_name, canonical
                )
                continue
            try:
                fetched = provider.fetch(provider_symbol, canonical)
            except Exception as exc:
                stats.failed += 1
                logger.warning(
                    "markets: %s via %s failed: %s", canonical, provider_name, exc
                )
                continue
            if fetched:
                candles.extend(fetched)
                stats.fetched += len(fetched)
                break
    return candles, stats.finish()
