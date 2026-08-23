"""RSS/Atom feed collector (sources.yaml: rss / macro.boj / macro.fed)."""
from __future__ import annotations

import calendar
from datetime import datetime, timezone
from typing import Any

import feedparser

from collectors.base import RawItem, RunStats, get_text, logger

COLLECTOR = "rss"


def struct_to_utc(st: Any) -> datetime | None:
    if not st:
        return None
    return datetime.fromtimestamp(calendar.timegm(st), tz=timezone.utc)


def parse_feed(text: str, source_cfg: dict) -> list[RawItem]:
    parsed = feedparser.parse(text)
    items: list[RawItem] = []
    for entry in parsed.entries:
        external_id = entry.get("id") or entry.get("link") or ""
        if not external_id:
            continue
        published = struct_to_utc(
            entry.get("published_parsed") or entry.get("updated_parsed")
        )
        summary = entry.get("summary", "")
        items.append(
            RawItem(
                source_id=source_cfg["id"],
                external_id=external_id,
                kind="article",
                title=entry.get("title", ""),
                url=entry.get("link", ""),
                published_at=published,
                country=source_cfg.get("country", ""),
                language=source_cfg.get("language", ""),
                category=source_cfg.get("category", ""),
                payload={"summary": summary[:2000]},
            )
        )
    return items


def _sources(config: dict | list) -> list[dict]:
    if isinstance(config, dict):
        return config.get("sources") or config.get("rss") or []
    return list(config)


def collect(config: dict) -> tuple[list[RawItem], RunStats]:
    stats = RunStats(collector=COLLECTOR)
    items: list[RawItem] = []
    for source in _sources(config):
        if source.get("method") != "rss" or source.get("enabled") is False:
            continue
        try:
            text = get_text(source["url"])
            feed_items = parse_feed(text, source)
        except Exception as exc:
            stats.failed += 1
            logger.warning("rss: feed %s failed: %s", source.get("id"), exc)
            continue
        items.extend(feed_items)
        stats.fetched += len(feed_items)
    return items, stats.finish()
