"""スコア済みアイテムからの Event 抽出 (ルールベース MVP)。

- score >= event_threshold のアイテムを対象
- entities.yaml の alias でエンティティ照合
- topics.yaml の event_type_hints で event_type 推定
- 同一 (event_type, 主エンティティ, 日付) はひとつの Event に統合し source_count を加算

AI による高度なイベント統合は Phase 3 (Workers AI) で上書き可能な構造。
"""
from __future__ import annotations

from typing import Any

from pipeline.normalize.normalizer import NormalizedItem

DEFAULT_EVENT_TYPE_BY_KIND = {
    "paper": "research",
    "repo": "model_release",
    "model": "model_release",
    "filing": "earnings",
}


def match_entities(text: str, entities_cfg: list[dict[str, Any]]) -> list[str]:
    low = f" {text.lower()} "
    matched = []
    for ent in entities_cfg:
        for alias in ent.get("aliases", []):
            a = alias.lower()
            # 短い alias の誤爆を避けるため単語境界っぽい判定
            if f" {a} " in low or low.startswith(f"{a} ") or f" {a}." in low or f" {a}," in low:
                matched.append(ent["id"])
                break
    return matched


def classify_event_type(item: NormalizedItem, hints: dict[str, list[str]]) -> str:
    text = f"{item.title} {item.summary}".lower()
    if item.category == "central_bank":
        return "central_bank"
    for event_type, keywords in hints.items():
        if any(kw.lower() in text for kw in keywords):
            return event_type
    return DEFAULT_EVENT_TYPE_BY_KIND.get(item.kind, "product_launch")


def build_events(
    items: list[NormalizedItem],
    entities_cfg: list[dict[str, Any]],
    hints: dict[str, list[str]],
    threshold: float = 60.0,
) -> list[dict[str, Any]]:
    events: dict[tuple[str, str, str], dict[str, Any]] = {}
    for item in items:
        if item.score < threshold:
            continue
        matched = match_entities(f"{item.title} {item.summary}", entities_cfg)
        # エンティティが特定できない記事はイベント化しない。
        # Event の存在意義は Entity -> Ticker -> 市場価格へ辿れることにあり
        # (docs/architecture.md)、紐付け先が無いものは記事のままで十分。
        # ここを緩めると記事がほぼ 1:1 でイベント化してノイズになる。
        if not matched:
            continue
        event_type = classify_event_type(item, hints)
        occurred = item.published_at or item.fetched_at
        day = (occurred or "")[:10]
        primary = matched[0]
        key = (event_type, primary, day)

        if key in events:
            ev = events[key]
            ev["source_count"] += 1
            ev["importance"] = max(ev["importance"], item.score)
            ev["entities"] = sorted(set(ev["entities"]) | set(matched))
            ev["topics"] = sorted(set(ev["topics"]) | set(item.topics))
        else:
            events[key] = {
                "event_type": event_type,
                "title": item.title[:300],
                "summary": item.summary[:500],
                "occurred_at": occurred,
                "country": item.country or "",
                "importance": item.score,
                "topics": list(item.topics),
                "entities": matched,
                "source_count": 1,
            }
    return sorted(events.values(), key=lambda e: e["importance"], reverse=True)
