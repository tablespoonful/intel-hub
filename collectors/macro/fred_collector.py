"""FRED macro series collector (markets.yaml: fred_series)."""
from __future__ import annotations

import os
from datetime import timedelta

from collectors.base import RunStats, get_json, logger, utcnow
from collectors.markets.providers import FRED_OBSERVATIONS_URL, MacroValue

COLLECTOR = "fred"
OBSERVATION_WINDOW_DAYS = 30


def parse_observations(data: dict, series_cfg: dict) -> list[MacroValue]:
    values: list[MacroValue] = []
    for obs in data.get("observations", []):
        raw = obs.get("value", ".")
        value = None if raw in (".", "", None) else float(raw)
        values.append(
            MacroValue(
                series_id=series_cfg["id"],
                date=obs.get("date", ""),
                value=value,
                name=series_cfg.get("name", ""),
                source="fred",
                country=series_cfg.get("country", ""),
            )
        )
    return values


def _series_list(config: dict | list) -> list[dict]:
    if isinstance(config, dict):
        return config.get("fred_series") or config.get("series") or []
    return list(config)


def collect(config: dict) -> tuple[list[MacroValue], RunStats]:
    stats = RunStats(collector=COLLECTOR)
    api_key = os.environ.get("FRED_API_KEY")
    if not api_key:
        stats.error = "skipped: no API key"
        return [], stats.finish("success")

    observation_start = (utcnow() - timedelta(days=OBSERVATION_WINDOW_DAYS)).date().isoformat()
    values: list[MacroValue] = []
    for series in _series_list(config):
        try:
            data = get_json(
                FRED_OBSERVATIONS_URL,
                params={
                    "series_id": series["id"],
                    "api_key": api_key,
                    "file_type": "json",
                    "observation_start": observation_start,
                },
            )
        except Exception as exc:
            stats.failed += 1
            logger.warning("fred: series %s failed: %s", series.get("id"), exc)
            continue
        series_values = parse_observations(data, series)
        values.extend(series_values)
        stats.fetched += len(series_values)
    return values, stats.finish()
