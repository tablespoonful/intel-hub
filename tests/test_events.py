from datetime import datetime, timedelta, timezone

from collectors.base import RawItem
from pipeline.events import build_events, classify_event_type, match_entities
from pipeline.normalize import normalize_item

ENTITIES = [
    {"id": "nvidia", "aliases": ["nvidia", "gr00t"], "tickers": ["NVDA"]},
    {"id": "openai", "aliases": ["openai", "chatgpt"], "tickers": []},
]
HINTS = {
    "model_release": ["release", "introducing"],
    "funding": ["raises", "funding"],
}


def make(title, score=80.0, country="US", published="2026-08-23T10:00:00Z"):
    item = normalize_item(RawItem(
        source_id="s", external_id=title[:24], kind="article", title=title,
        published_at=datetime(2026, 8, 23, 10, tzinfo=timezone.utc), country=country))
    item.score = score
    return item


def test_match_entities():
    assert match_entities("NVIDIA announces GR00T update", ENTITIES) == ["nvidia"]
    assert match_entities("nothing relevant here", ENTITIES) == []


def test_classify_event_type():
    assert classify_event_type(make("Introducing our new model"), HINTS) == "model_release"
    assert classify_event_type(make("Startup raises $100M"), HINTS) == "funding"


def test_build_events_threshold():
    events = build_events([make("NVIDIA release", score=50)], ENTITIES, HINTS, threshold=60)
    assert events == []


def test_items_without_entity_do_not_become_events():
    """エンティティ不明の記事はイベント化しない (ticker へ辿れないため)。

    これを許すと記事がほぼ 1:1 でイベント化し、実測で 840 件まで膨らんだ。
    """
    noise = make("Some unrelated blog post about gardening", score=95)
    assert build_events([noise], ENTITIES, HINTS, threshold=60) == []


def test_build_events_merges_same_entity_same_day():
    a = make("NVIDIA releases new robot model", score=85)
    b = make("NVIDIA introducing GR00T v2 today", score=70)
    events = build_events([a, b], ENTITIES, HINTS, threshold=60)
    assert len(events) == 1
    ev = events[0]
    assert ev["source_count"] == 2
    assert ev["importance"] == 85
    assert "nvidia" in ev["entities"]
    assert ev["event_type"] == "model_release"


def make_at(title, when, score=80.0):
    item = normalize_item(RawItem(
        source_id="s", external_id=title[:24], kind="article", title=title,
        published_at=when, country="US"))
    item.score = score
    return item


def test_build_events_skips_items_older_than_max_age():
    """古いアイテムはイベント化しない。

    Event は毎回バッチだけから組み立て直されるため、古いイベントを作り直すと
    source_count と topics がバッチ構成で揺れ、D1 の書き込み枠を消費し続ける。
    """
    now = datetime.now(timezone.utc)
    fresh = make_at("NVIDIA release today", now - timedelta(hours=1))
    stale = make_at("NVIDIA release long ago", now - timedelta(days=10))

    events = build_events([fresh, stale], ENTITIES, HINTS, threshold=60, max_age_days=3)
    assert [e["title"] for e in events] == ["NVIDIA release today"]

    # max_age_days を渡さなければ従来どおり全件対象 (rescore など再構築用途)。
    assert len(build_events([fresh, stale], ENTITIES, HINTS, threshold=60)) == 2
