from datetime import datetime, timezone

from collectors.base import RawItem
from pipeline.normalize import (
    canonical_url,
    detect_language,
    normalize_item,
    normalize_title,
    to_utc_iso,
)


def test_canonical_url_strips_tracking_params():
    url = "https://Example.com/post/?utm_source=x&utm_medium=rss&id=42&fbclid=abc"
    assert canonical_url(url) == "https://example.com/post?id=42"


def test_canonical_url_strips_fragment_and_trailing_slash():
    assert canonical_url("https://a.com/path/#section") == "https://a.com/path"
    assert canonical_url("https://a.com/") == "https://a.com/"


def test_normalize_title_nfkc_and_case():
    assert normalize_title("  GPT-5:  The <b>Next</b> Step!! ") == "gpt 5 the next step"
    assert normalize_title("ＮＶＩＤＩＡが発表") == "nvidiaが発表"


def test_detect_language():
    assert detect_language("大規模言語モデルのニュース") == "ja"
    assert detect_language("阿里巴巴发布新模型") == "zh"
    assert detect_language("New model released") == "en"


def test_to_utc_iso_handles_naive_and_aware():
    aware = datetime(2026, 8, 23, 12, 0, tzinfo=timezone.utc)
    assert to_utc_iso(aware) == "2026-08-23T12:00:00Z"
    naive = datetime(2026, 8, 23, 12, 0)
    assert to_utc_iso(naive) == "2026-08-23T12:00:00Z"
    assert to_utc_iso(None) is None


def test_normalize_item_full():
    raw = RawItem(
        source_id="openai-news",
        external_id="abc",
        kind="article",
        title="Introducing &amp; testing <em>GPT-5</em>",
        url="https://openai.com/news/gpt5?utm_source=rss",
        published_at=datetime(2026, 8, 22, 9, 30, tzinfo=timezone.utc),
        country="US",
        payload={"summary": "<p>A new model.</p>"},
    )
    item = normalize_item(raw)
    assert item.title == "Introducing & testing GPT-5"
    assert item.canonical_url == "https://openai.com/news/gpt5"
    assert item.published_at == "2026-08-22T09:30:00Z"
    assert item.summary == "A new model."
    assert item.language == "en"
    assert item.raw_hash == raw.raw_hash
