from datetime import datetime, timezone

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
