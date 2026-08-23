"""Collector parse 関数のテスト (実 API は呼ばず fixture を使用)。"""
from collectors.ai.hackernews_collector import matches_keywords, parse_hn_item, topic_keywords
from collectors.ai.huggingface_collector import parse_model
from collectors.ai.rss_collector import parse_feed
from collectors.github.github_collector import parse_repo
from collectors.macro.fred_collector import parse_observations
from collectors.macro.sec_edgar_collector import filing_url, parse_submissions
from collectors.markets.providers import (
    parse_coinbase_candles,
    parse_frankfurter,
    parse_fred_candles,
)
from collectors.papers.arxiv_collector import arxiv_id_from_entry_id, parse_arxiv
from collectors.youtube.youtube_collector import parse_playlist_item, uploads_playlists

RSS_FIXTURE = """<?xml version="1.0"?>
<rss version="2.0"><channel><title>Test Feed</title>
<item>
  <title>Introducing GPT-6</title>
  <link>https://example.com/gpt6?utm_source=rss</link>
  <guid>https://example.com/gpt6</guid>
  <pubDate>Sat, 22 Aug 2026 09:00:00 GMT</pubDate>
  <description>A new frontier model.</description>
</item>
</channel></rss>"""

ARXIV_FIXTURE = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/2608.12345v2</id>
    <title>Diffusion Policy for Humanoid Robot Manipulation</title>
    <summary>We present a robot learning method.</summary>
    <published>2026-08-20T00:00:00Z</published>
    <author><name>Alice</name></author>
    <category term="cs.RO"/>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/2608.99999v1</id>
    <title>A Study of Sorting Algorithms</title>
    <summary>Classic algorithms revisited.</summary>
    <published>2026-08-20T00:00:00Z</published>
    <author><name>Bob</name></author>
    <category term="cs.DS"/>
  </entry>
</feed>"""

TOPICS = {"topics": {"robotics": {"weight": 1.0, "keywords": ["robot", "humanoid"]},
                     "llm": {"weight": 1.0, "keywords": ["gpt", "language model"]}}}


def test_parse_feed():
    items = parse_feed(RSS_FIXTURE, {"id": "test-src", "country": "US",
                                     "language": "en", "category": "llm"})
    assert len(items) == 1
    it = items[0]
    assert it.source_id == "test-src"
    assert it.external_id == "https://example.com/gpt6"
    assert it.kind == "article"
    assert it.published_at.year == 2026
    assert it.payload["summary"] == "A new frontier model."


def test_parse_hn_item_and_filters():
    item = parse_hn_item({"id": 1, "type": "story", "title": "New LLM agent framework",
                          "score": 120, "descendants": 45, "time": 1787000000,
                          "url": "https://example.com/x"})
    assert item.kind == "hn"
    assert item.payload["points"] == 120
    assert parse_hn_item({"id": 2, "type": "comment", "title": "x"}) is None
    assert parse_hn_item({"id": 3, "type": "story", "title": "y", "dead": True}) is None
    # Ask HN (url なし) は HN パーマリンクになる
    ask = parse_hn_item({"id": 4, "type": "story", "title": "Ask HN: robots?"})
    assert ask.url == "https://news.ycombinator.com/item?id=4"

    kws = topic_keywords(TOPICS)
    assert matches_keywords("A humanoid ROBOT demo", kws)
    assert not matches_keywords("Cooking recipes", kws)


def test_parse_arxiv_filters_by_topic():
    items = parse_arxiv(ARXIV_FIXTURE, TOPICS)
    assert len(items) == 1
    it = items[0]
    assert it.external_id == "2608.12345"          # バージョン除去
    assert it.kind == "paper"
    assert "robotics" in it.tags
    assert it.payload["authors"] == ["Alice"]
    assert it.payload["categories"] == ["cs.RO"]


def test_arxiv_id_version_strip():
    assert arxiv_id_from_entry_id("http://arxiv.org/abs/2608.12345v10") == "2608.12345"
    assert arxiv_id_from_entry_id("http://arxiv.org/abs/2608.12345") == "2608.12345"


def test_parse_repo():
    repo = {"full_name": "org/repo", "html_url": "https://github.com/org/repo",
            "description": "d", "language": "Python", "topics": ["ai"],
            "stargazers_count": 1500, "forks_count": 30, "open_issues_count": 7,
            "pushed_at": "2026-08-22T10:00:00Z"}
    release = {"tag_name": "v1.2.0", "published_at": "2026-08-21T00:00:00Z"}
    item = parse_repo(repo, release)
    assert item.external_id == "org/repo"
    assert item.kind == "repo"
    assert item.payload["stars"] == 1500
    assert item.payload["latest_release"] == "v1.2.0"
    no_release = parse_repo(repo, None)
    assert no_release.payload.get("latest_release") in (None, "")


def test_parse_model():
    item = parse_model({"id": "org/cool-vla", "downloads": 1234, "likes": 56,
                        "pipeline_tag": "robotics", "tags": ["vla"],
                        "createdAt": "2026-08-01T00:00:00Z",
                        "lastModified": "2026-08-20T12:00:00Z"})
    assert item.external_id == "org/cool-vla"
    assert item.kind == "model"
    assert item.payload["downloads"] == 1234
    assert item.published_at.day == 20
    assert parse_model({}) is None


def test_sec_edgar_parse_and_url():
    data = {"filings": {"recent": {
        "form": ["8-K", "S-8", "10-Q"],
        "accessionNumber": ["0001045810-26-000100", "0001045810-26-000101",
                            "0001045810-26-000102"],
        "filingDate": ["2026-08-20", "2026-08-19", "2026-08-18"],
        "primaryDocument": ["a.htm", "b.htm", "c.htm"],
    }}}
    company = {"cik": "0001045810", "ticker": "NVDA", "name": "NVIDIA"}
    items = parse_submissions(data, company, ["8-K", "10-Q"])
    assert len(items) == 2
    assert items[0].title == "NVIDIA 8-K filing"
    assert items[0].url == \
        "https://www.sec.gov/Archives/edgar/data/1045810/000104581026000100/a.htm"
    assert filing_url("0000002488", "0000002488-26-000001", "x.htm") == \
        "https://www.sec.gov/Archives/edgar/data/2488/000000248826000001/x.htm"


def test_parse_fred_observations():
    data = {"observations": [
        {"date": "2026-08-20", "value": "4.25"},
        {"date": "2026-08-21", "value": "."},
    ]}
    values = parse_observations(data, {"id": "DGS10", "name": "US 10Y", "country": "US"})
    dates = {v.date: v.value for v in values}
    assert dates["2026-08-20"] == 4.25
    # "." (欠損) は None または除外のどちらかであること
    assert dates.get("2026-08-21") is None


def test_market_provider_parsers():
    fx = parse_frankfurter({"base": "USD", "date": "2026-08-22",
                            "rates": {"JPY": 148.5}}, "JPY", "USDJPY")
    assert len(fx) == 1
    assert fx[0].close == 148.5
    assert fx[0].interval == "1d"
    assert fx[0].provider == "frankfurter"

    fred = parse_fred_candles({"observations": [
        {"date": "2026-08-21", "value": "6500.5"},
        {"date": "2026-08-22", "value": "."}]}, "SPX")
    assert len(fred) == 1
    assert fred[0].close == 6500.5

    cb = parse_coinbase_candles(
        [[1787000000, 100.0, 110.0, 105.0, 108.0, 12.5],
         [1786999100, 99.0, 106.0, 100.0, 105.0, 10.0]], "BTC")
    assert len(cb) == 2
    assert cb[-1].close == 108.0            # 時刻昇順
    assert cb[0].interval == "15m"


def test_youtube_parsers():
    playlists = uploads_playlists({"items": [
        {"id": "UC123", "contentDetails": {"relatedPlaylists": {"uploads": "UU123"}}}]})
    assert playlists == {"UC123": "UU123"}
    item = parse_playlist_item(
        {"snippet": {"resourceId": {"videoId": "abc"}, "title": "Robot demo",
                     "publishedAt": "2026-08-22T00:00:00Z", "description": "d"}},
        {"id": "UC123", "name": "TestCh", "country": "US"})
    assert item.external_id == "abc"
    assert item.url == "https://www.youtube.com/watch?v=abc"
    assert item.payload["channel_name"] == "TestCh"
