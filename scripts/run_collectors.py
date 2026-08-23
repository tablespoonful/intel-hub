"""Collector 実行ランナー。

使い方:
    python -m scripts.run_collectors --tier fast|normal|slow|all [--sink auto|sqlite|worker] [--db data/intel.db]

- tier ごとに対象 collector を実行し、normalize → dedupe → scoring → events を通して sink へ書く
- sink=auto: INTEL_HUB_INGEST_URL があれば worker、無ければ sqlite
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from typing import Any

from collectors.base import RunStats, logger
from pipeline import config as cfg
from pipeline.dedupe import dedupe_batch
from pipeline.events import build_events
from pipeline.normalize import normalize_item
from pipeline.scoring import Scorer
from scripts.env import load_dotenv
from scripts.sinks import SQLiteSink, WorkerSink

TIERS = {
    "fast": ["hackernews", "macro_rss", "markets"],
    "normal": ["rss", "github", "huggingface"],
    "slow": ["arxiv", "youtube", "fred", "sec_edgar", "rss_slow"],
}

BUILTIN_SOURCES: list[dict[str, Any]] = [
    {"id": "hackernews", "name": "Hacker News", "method": "api",
     "url": "https://hacker-news.firebaseio.com", "quality": 0.6, "tier": "fast"},
    {"id": "arxiv", "name": "arXiv", "method": "api",
     "url": "https://export.arxiv.org", "quality": 0.75, "tier": "slow", "category": "research"},
    {"id": "github", "name": "GitHub", "method": "api",
     "url": "https://api.github.com", "quality": 0.75, "tier": "normal"},
    {"id": "huggingface", "name": "Hugging Face Hub", "method": "api",
     "url": "https://huggingface.co", "quality": 0.7, "tier": "normal"},
    {"id": "youtube", "name": "YouTube", "method": "api",
     "url": "https://www.googleapis.com/youtube/v3", "quality": 0.6, "tier": "slow"},
    {"id": "sec-edgar", "name": "SEC EDGAR", "method": "api",
     "url": "https://data.sec.gov", "quality": 0.9, "tier": "slow", "country": "US",
     "category": "earnings"},
]


def _rss_sources(tier: str | None = None) -> list[dict[str, Any]]:
    src = [s for s in cfg.sources().get("rss", []) if s.get("enabled") is not False
           and s.get("method") == "rss"]
    if tier:
        src = [s for s in src if s.get("tier", "normal") == tier]
    return src


def _macro_rss_sources() -> list[dict[str, Any]]:
    macro = cfg.sources().get("macro", {})
    out = []
    for group in ("boj", "fed"):
        out += [s for s in macro.get(group, []) if s.get("enabled") is not False
                and s.get("method") == "rss"]
    return out


def run_collector(name: str) -> tuple[list, list, list, list[RunStats]]:
    """(raw_items, candles, macro_values, stats_list) を返す。"""
    items, candles, macro_values, stats = [], [], [], []
    if name == "rss":
        from collectors.ai import rss_collector
        i, s = rss_collector.collect({"rss": _rss_sources("normal")})
        items, stats = i, [s]
    elif name == "rss_slow":
        from collectors.ai import rss_collector
        i, s = rss_collector.collect({"rss": _rss_sources("slow")})
        s.collector = "rss_slow"
        items, stats = i, [s]
    elif name == "macro_rss":
        from collectors.ai import rss_collector
        i, s = rss_collector.collect({"rss": _macro_rss_sources()})
        s.collector = "macro_rss"
        items, stats = i, [s]
    elif name == "hackernews":
        from collectors.ai import hackernews_collector
        conf = dict(cfg.sources().get("hackernews", {}))
        conf["topics"] = cfg.topics()
        i, s = hackernews_collector.collect(conf)
        items, stats = i, [s]
    elif name == "huggingface":
        from collectors.ai import huggingface_collector
        i, s = huggingface_collector.collect(cfg.sources().get("huggingface", {}))
        items, stats = i, [s]
    elif name == "arxiv":
        from collectors.papers import arxiv_collector
        conf = dict(cfg.sources().get("arxiv", {}))
        conf["topics"] = cfg.topics()
        i, s = arxiv_collector.collect(conf)
        items, stats = i, [s]
    elif name == "github":
        from collectors.github import github_collector
        i, s = github_collector.collect(cfg.sources().get("github", {}))
        items, stats = i, [s]
    elif name == "youtube":
        from collectors.youtube import youtube_collector
        i, s = youtube_collector.collect(cfg.sources().get("youtube", {}))
        items, stats = i, [s]
    elif name == "sec_edgar":
        from collectors.macro import sec_edgar_collector
        i, s = sec_edgar_collector.collect(cfg.sources().get("macro", {}).get("sec_edgar", {}))
        items, stats = i, [s]
    elif name == "fred":
        from collectors.macro import fred_collector
        mv, s = fred_collector.collect(cfg.markets())
        macro_values, stats = mv, [s]
    elif name == "markets":
        from collectors.markets import market_collector
        cd, s = market_collector.collect(cfg.markets())
        candles, stats = cd, [s]
    else:
        raise ValueError(f"unknown collector: {name}")
    return items, candles, macro_values, stats


def catalog_sources() -> list[dict[str, Any]]:
    return (BUILTIN_SOURCES + _rss_sources("normal") + _rss_sources("slow")
            + _rss_sources("fast") + _macro_rss_sources())


def make_sink(kind: str, db_path: str):
    if kind == "auto":
        kind = "worker" if os.environ.get("INTEL_HUB_INGEST_URL") else "sqlite"
    if kind == "worker":
        url = os.environ.get("INTEL_HUB_INGEST_URL", "")
        token = os.environ.get("INTEL_HUB_INGEST_TOKEN", "")
        if not url or not token:
            raise SystemExit("worker sink には INTEL_HUB_INGEST_URL / INTEL_HUB_INGEST_TOKEN が必要です")
        logger.info("sink: worker (%s)", url)
        return WorkerSink(url, token)
    logger.info("sink: sqlite (%s)", db_path)
    return SQLiteSink(db_path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tier", choices=[*TIERS, "all"], default="all")
    parser.add_argument("--sink", choices=["auto", "sqlite", "worker"], default="auto")
    parser.add_argument("--db", default="data/intel.db")
    parser.add_argument("--only", help="単一 collector 名を指定して実行 (デバッグ用)")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    load_dotenv()

    names = ([args.only] if args.only
             else TIERS[args.tier] if args.tier != "all"
             else [n for t in TIERS.values() for n in t])

    all_items, all_candles, all_macro, all_stats = [], [], [], []
    item_collector: dict[tuple[str, str], str] = {}   # (source_id, external_id) -> collector名
    for name in names:
        logger.info("=== collector: %s ===", name)
        try:
            items, candles, macro_values, stats = run_collector(name)
        except Exception as exc:  # collector は raise しない契約だが最終防御
            logger.exception("collector %s crashed", name)
            stats = [RunStats(collector=name).finish("failed")]
            stats[0].error = str(exc)[:500]
            items, candles, macro_values = [], [], []
        for it in items:
            item_collector[(it.source_id, it.external_id)] = stats[0].collector
        all_items += items
        all_candles += candles
        all_macro += macro_values
        all_stats += stats

    quality = cfg.source_quality_map()
    normalized = [normalize_item(r) for r in all_items]
    unique, duplicates = dedupe_batch(normalized, quality)

    dup_by_collector: dict[str, int] = {}
    for d in duplicates:
        coll = item_collector.get((d.source_id, d.external_id), "")
        dup_by_collector[coll] = dup_by_collector.get(coll, 0) + 1
    for s in all_stats:
        s.duplicate += dup_by_collector.get(s.collector, 0)

    scoring_cfg = cfg.scoring()
    scorer = Scorer(scoring_cfg, cfg.topics(), quality)
    scored = scorer.score_batch(unique)

    events = build_events(
        scored, cfg.entities(),
        cfg.topics().get("event_type_hints", {}),
        threshold=float(scoring_cfg.get("event_threshold", 60)))

    sink = make_sink(args.sink, args.db)
    counts = sink.write(catalog_sources(), scored, all_candles, all_macro, events, all_stats)

    logger.info("fetched=%d unique=%d dup(batch)=%d candles=%d macro=%d events=%d",
                len(all_items), len(scored), len(duplicates), len(all_candles),
                len(all_macro), len(events))
    logger.info("sink counts: %s", counts)

    failed = [s for s in all_stats if s.status == "failed"]
    if failed and len(failed) == len(all_stats):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
