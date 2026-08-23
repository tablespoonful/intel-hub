from datetime import datetime, timedelta, timezone

from collectors.base import RawItem
from pipeline import config as cfg
from pipeline.normalize import normalize_item
from pipeline.scoring import Scorer

NOW = datetime(2026, 8, 23, 12, 0, tzinfo=timezone.utc)

SCORING_CFG = {
    "weights": {"recency": 0.25, "source_quality": 0.20, "relevance": 0.20,
                "velocity": 0.15, "popularity": 0.10, "novelty": 0.10},
    "recency": {"half_life_hours": 24},
    "popularity": {"saturation": {"hn_points": 500, "stars": 20000}},
    "velocity": {"saturation": {"stars_24h_delta": 300, "stars_7d_delta": 1500}},
    "ai_threshold": 65,
    "negative_keyword_penalty": 15,
}
TOPICS_CFG = {
    "topics": {
        "llm": {"weight": 1.0, "keywords": ["llm", "language model", "gpt"]},
        "robotics": {"weight": 1.0, "keywords": ["robot", "humanoid"]},
    },
    "negative_keywords": ["webinar"],
}
QUALITY = {"good-src": 0.95, "bad-src": 0.2}


def scorer():
    return Scorer(SCORING_CFG, TOPICS_CFG, QUALITY, now=NOW)


def make(title, source_id="good-src", published=None, kind="article", payload=None):
    return normalize_item(RawItem(
        source_id=source_id, external_id=title[:20], kind=kind, title=title,
        published_at=published or NOW - timedelta(hours=1),
        payload=payload or {}))


def test_score_range_and_components():
    item = scorer().score(make("New LLM released with robot demo"))
    assert 0 <= item.score <= 100
    assert set(item.score_components) == {
        "recency", "source_quality", "relevance", "velocity", "popularity", "novelty"}
    assert set(item.topics) == {"llm", "robotics"}


def test_fresh_beats_stale():
    s = scorer()
    fresh = s.score(make("GPT news", published=NOW - timedelta(hours=1)))
    stale = s.score(make("GPT news old", published=NOW - timedelta(days=14)))
    assert fresh.score > stale.score


def test_relevant_beats_irrelevant():
    s = scorer()
    rel = s.score(make("A new language model beats benchmarks"))
    irr = s.score(make("Quarterly gardening tips for beginners"))
    assert rel.score > irr.score
    assert irr.topics == []


def test_source_quality_matters():
    s = scorer()
    good = s.score(make("Robot humanoid launch", source_id="good-src"))
    bad = s.score(make("Robot humanoid launch2", source_id="bad-src"))
    assert good.score > bad.score


def test_negative_keyword_penalty():
    s = scorer()
    normal = s.score(make("LLM product update"))
    spam = s.score(make("LLM product update webinar"))
    assert normal.score - spam.score >= 10


def test_ai_status_threshold():
    s = scorer()
    hot = s.score(make("New humanoid robot LLM gpt release",
                       payload={"points": 400}, kind="hn"))
    cold = s.score(make("boring unrelated post", source_id="bad-src",
                        published=NOW - timedelta(days=30)))
    assert cold.ai_status == "none"
    assert hot.ai_status == ("pending" if hot.score >= 65 else "none")


def test_real_config_files_load():
    s = Scorer(cfg.scoring(), cfg.topics(), cfg.source_quality_map(), now=NOW)
    item = s.score(make("NVIDIA announces new humanoid robot foundation model"))
    assert item.score > 0
