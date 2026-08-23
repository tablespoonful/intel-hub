from datetime import datetime, timezone

from collectors.base import RawItem
from pipeline.dedupe import dedupe_batch, title_similarity
from pipeline.normalize import normalize_item


def make(source_id, external_id, title, url="", kind="article"):
    return normalize_item(RawItem(
        source_id=source_id, external_id=external_id, kind=kind,
        title=title, url=url,
        published_at=datetime(2026, 8, 23, tzinfo=timezone.utc)))


def test_exact_external_id_dedupe():
    a = make("s1", "x", "Title A")
    b = make("s1", "x", "Title A")
    unique, dups = dedupe_batch([a, b])
    assert len(unique) == 1
    assert len(dups) == 1


def test_canonical_url_dedupe():
    a = make("s1", "1", "OpenAI releases GPT-5", "https://openai.com/gpt5?utm_source=a")
    b = make("s2", "2", "Totally different headline", "https://openai.com/gpt5")
    unique, dups = dedupe_batch([a, b])
    assert len(unique) == 1
    assert dups[0].dedupe_of is not None


def test_similar_title_dedupe():
    a = make("s1", "1", "NVIDIA announces new Physical AI platform GR00T")
    b = make("s2", "2", "NVIDIA announces new Physical AI platform GR00T!")
    unique, dups = dedupe_batch([a, b])
    assert len(unique) == 1


def test_different_items_not_deduped():
    a = make("s1", "1", "OpenAI releases GPT-5")
    b = make("s2", "2", "Toyota unveils humanoid robot for factories")
    unique, dups = dedupe_batch([a, b])
    assert len(unique) == 2
    assert not dups


def test_higher_quality_source_wins():
    low = make("low-src", "1", "Big AI announcement today")
    high = make("high-src", "2", "Big AI announcement today")
    unique, dups = dedupe_batch([low, high], quality={"low-src": 0.3, "high-src": 0.9})
    assert unique[0].source_id == "high-src"
    assert dups[0].source_id == "low-src"
    assert dups[0].dedupe_of == "high-src:2"


def test_title_similarity_bounds():
    assert title_similarity("", "abc") == 0.0
    assert title_similarity("same title", "same title") == 1.0
