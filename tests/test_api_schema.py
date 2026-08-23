"""AI レスポンス schema と ingest ペイロード契約のテスト。"""
import json
from dataclasses import asdict
from datetime import datetime, timezone

from collectors.base import RawItem
from pipeline.ai import AI_RESPONSE_SCHEMA
from pipeline.normalize import normalize_item


def test_ai_schema_is_strict():
    assert AI_RESPONSE_SCHEMA["additionalProperties"] is False
    assert set(AI_RESPONSE_SCHEMA["required"]) == set(AI_RESPONSE_SCHEMA["properties"].keys())
    for field in ("importance", "novelty", "market_relevance", "technology_relevance"):
        prop = AI_RESPONSE_SCHEMA["properties"][field]
        assert prop["minimum"] == 0 and prop["maximum"] == 100


def test_normalized_item_matches_ingest_contract():
    """dev-spec §3 の items[] に必要なキーが NormalizedItem に揃っている。"""
    item = normalize_item(RawItem(
        source_id="s", external_id="e", kind="article", title="t",
        url="https://x.com/a", published_at=datetime(2026, 8, 23, tzinfo=timezone.utc)))
    d = asdict(item)
    required = {
        "source_id", "external_id", "kind", "url", "canonical_url", "title",
        "normalized_title", "summary", "published_at", "fetched_at", "country",
        "language", "category", "tags", "topics", "score", "score_components",
        "ai_status", "raw_hash", "payload",
    }
    assert required <= set(d.keys())
    json.dumps(d)  # JSON 直列化可能であること
