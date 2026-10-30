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


def test_worker_sink_sends_market_symbols_with_prices(monkeypatch):
    """dev-spec §3: market_prices を送る回は markets.yaml の銘柄定義も market_symbols[] で送る。"""
    from collectors.markets.providers import Candle
    from scripts import sinks

    sent = []

    class _Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"ok": True, "inserted": {}, "duplicates": 0}

    monkeypatch.setattr(sinks.httpx, "post", lambda url, json, **kw: sent.append(json) or _Resp())
    sink = sinks.WorkerSink("https://example.invalid", "token")

    candle = Candle(symbol="US10Y", ts="2026-10-29T00:00:00Z", interval="1d",
                    open=4.1, high=4.1, low=4.1, close=4.1, volume=None, provider="fred")
    sink.write([], [], [candle], [], [], [])
    sink.write([], [], [], [], [], [])

    symbols = {s["canonical"]: s for s in sent[0]["market_symbols"]}
    assert symbols["US10Y"]["asset"] == "rate"
    assert symbols["SPX"]["name"] == "S&P 500"
    assert set(symbols["USDJPY"]) == {"canonical", "name", "asset", "country", "providers"}
    assert sent[1]["market_symbols"] == []  # 価格の無い回は送らない
    json.dumps(sent[0])
