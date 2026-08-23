"""Hugging Face model search collector (sources.yaml: huggingface)."""
from __future__ import annotations

import os
from datetime import datetime, timezone

from dateutil import parser as dateparser

from collectors.base import RawItem, RunStats, get_json, logger

COLLECTOR = "huggingface"
API_URL = "https://huggingface.co/api/models"


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = dateparser.isoparse(value)
    except (ValueError, TypeError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def parse_model(model: dict) -> RawItem | None:
    model_id = model.get("id") or model.get("modelId")
    if not model_id:
        return None
    published = _parse_dt(model.get("lastModified")) or _parse_dt(model.get("createdAt"))
    return RawItem(
        source_id="huggingface",
        external_id=model_id,
        kind="model",
        title=model_id,
        url=f"https://huggingface.co/{model_id}",
        published_at=published,
        payload={
            "downloads": model.get("downloads", 0),
            "likes": model.get("likes", 0),
            "pipeline_tag": model.get("pipeline_tag", ""),
            "tags": model.get("tags", []),
            "createdAt": model.get("createdAt", ""),
        },
    )


def collect(config: dict) -> tuple[list[RawItem], RunStats]:
    stats = RunStats(collector=COLLECTOR)
    items: list[RawItem] = []
    headers: dict[str, str] | None = None
    token = os.environ.get("HF_TOKEN")
    if token:
        headers = {"Authorization": f"Bearer {token}"}
    limit = config.get("limit_per_keyword", 30)
    seen: set[str] = set()
    for keyword in config.get("search_keywords", []):
        try:
            models = get_json(
                API_URL,
                headers=headers,
                params={
                    "search": keyword,
                    "sort": "lastModified",
                    "direction": -1,
                    "limit": limit,
                },
            )
        except Exception as exc:
            stats.failed += 1
            logger.warning("huggingface: keyword %r failed: %s", keyword, exc)
            continue
        for model in models:
            item = parse_model(model)
            if item is None or item.external_id in seen:
                continue
            seen.add(item.external_id)
            items.append(item)
            stats.fetched += 1
    return items, stats.finish()
