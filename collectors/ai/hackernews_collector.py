"""Hacker News collector (sources.yaml: hackernews + topics.yaml)."""
from __future__ import annotations

from datetime import datetime, timezone

from collectors.base import RawItem, RunStats, get_json, logger

COLLECTOR = "hackernews"
API_BASE = "https://hacker-news.firebaseio.com/v0"


def topic_keywords(topics_config: dict) -> list[str]:
    topics = topics_config.get("topics", topics_config) or {}
    keywords: list[str] = []
    for topic in topics.values():
        keywords.extend(k.lower() for k in topic.get("keywords", []))
    return keywords


def matches_keywords(title: str, keywords: list[str]) -> bool:
    lowered = title.lower()
    return any(kw in lowered for kw in keywords)


def parse_hn_item(item: dict) -> RawItem | None:
    if not item or item.get("deleted") or item.get("dead"):
        return None
    if item.get("type") != "story":
        return None
    item_id = item.get("id")
    title = item.get("title", "")
    if item_id is None or not title:
        return None
    hn_url = f"https://news.ycombinator.com/item?id={item_id}"
    published = None
    if item.get("time"):
        published = datetime.fromtimestamp(item["time"], tz=timezone.utc)
    return RawItem(
        source_id="hackernews",
        external_id=str(item_id),
        kind="hn",
        title=title,
        url=item.get("url") or hn_url,
        published_at=published,
        payload={
            "points": item.get("score", 0),
            "num_comments": item.get("descendants", 0),
            "hn_url": hn_url,
        },
    )


def collect(config: dict) -> tuple[list[RawItem], RunStats]:
    stats = RunStats(collector=COLLECTOR)
    items: list[RawItem] = []
    keywords = topic_keywords(config.get("topics", {}))
    lists = config.get("lists", ["topstories", "newstories"])
    max_items = config.get("max_items_per_list", 60)
    min_points_top = config.get("min_points_top", 0)

    id_lists: dict[str, list[int]] = {}
    try:
        for list_name in lists:
            id_lists[list_name] = get_json(f"{API_BASE}/{list_name}.json")[:max_items]
    except Exception as exc:
        stats.error = f"hackernews list fetch failed: {exc}"
        return items, stats.finish("failed")

    seen: set[int] = set()
    for list_name, ids in id_lists.items():
        for item_id in ids:
            if item_id in seen:
                continue
            seen.add(item_id)
            try:
                raw = get_json(f"{API_BASE}/item/{item_id}.json")
            except Exception as exc:
                stats.failed += 1
                logger.warning("hackernews: item %s failed: %s", item_id, exc)
                continue
            item = parse_hn_item(raw)
            if item is None:
                continue
            if list_name == "topstories" and item.payload["points"] < min_points_top:
                continue
            if not matches_keywords(item.title, keywords):
                continue
            items.append(item)
            stats.fetched += 1
    return items, stats.finish()
