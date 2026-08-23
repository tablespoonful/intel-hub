"""arXiv Atom API collector (sources.yaml: arxiv + topics.yaml)."""
from __future__ import annotations

import calendar
import re
from datetime import datetime, timezone
from typing import Any

import feedparser

from collectors.base import RawItem, RunStats, get_text, logger

COLLECTOR = "arxiv"
API_URL = "http://export.arxiv.org/api/query"
_VERSION_RE = re.compile(r"v\d+$")


def _struct_to_utc(st: Any) -> datetime | None:
    if not st:
        return None
    return datetime.fromtimestamp(calendar.timegm(st), tz=timezone.utc)


def arxiv_id_from_entry_id(entry_id: str) -> str:
    return _VERSION_RE.sub("", entry_id.rstrip("/").rsplit("/", 1)[-1])


def topic_keyword_map(topics_config: dict) -> dict[str, list[str]]:
    topics = topics_config.get("topics", topics_config) or {}
    return {
        name: [k.lower() for k in topic.get("keywords", [])]
        for name, topic in topics.items()
    }


def parse_arxiv(text: str, topics: dict) -> list[RawItem]:
    keyword_map = topic_keyword_map(topics)
    parsed = feedparser.parse(text)
    items: list[RawItem] = []
    for entry in parsed.entries:
        entry_id = entry.get("id", "")
        if not entry_id:
            continue
        title = entry.get("title", "").replace("\n", " ").strip()
        summary = entry.get("summary", "")
        haystack = f"{title}\n{summary}".lower()
        matched = [
            name
            for name, keywords in keyword_map.items()
            if any(kw in haystack for kw in keywords)
        ]
        if not matched:
            continue
        items.append(
            RawItem(
                source_id="arxiv",
                external_id=arxiv_id_from_entry_id(entry_id),
                kind="paper",
                title=title,
                url=entry.get("link", entry_id),
                published_at=_struct_to_utc(
                    entry.get("published_parsed") or entry.get("updated_parsed")
                ),
                tags=matched,
                payload={
                    "authors": [a.get("name", "") for a in entry.get("authors", [])],
                    "categories": [t.get("term", "") for t in entry.get("tags", [])],
                    "abstract": summary[:3000],
                },
            )
        )
    return items


def collect(config: dict) -> tuple[list[RawItem], RunStats]:
    stats = RunStats(collector=COLLECTOR)
    categories = config.get("categories", [])
    search_query = " OR ".join(f"cat:{c}" for c in categories)
    try:
        text = get_text(
            API_URL,
            params={
                "search_query": search_query,
                "sortBy": "submittedDate",
                "sortOrder": "descending",
                "max_results": config.get("max_results", 200),
            },
        )
    except Exception as exc:
        stats.error = f"arxiv query failed: {exc}"
        logger.warning("arxiv: %s", stats.error)
        return [], stats.finish("failed")
    items = parse_arxiv(text, config.get("topics", {}))
    stats.fetched = len(items)
    return items, stats.finish()
