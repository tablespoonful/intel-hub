"""既存ローカル SQLite の articles / papers を現行 config で再スコアリングする。

使い方:
    python -m scripts.rescore [--db data/intel.db]

raw_items を正とし、normalize → scoring を再適用する (`make score`)。
"""
from __future__ import annotations

import argparse
import json
import logging
import sqlite3
from datetime import datetime, timezone

from collectors.base import RawItem
from pipeline import config as cfg
from pipeline.normalize import normalize_item
from pipeline.scoring import Scorer


def _parse_dt(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="data/intel.db")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM raw_items").fetchall()

    scorer = Scorer(cfg.scoring(), cfg.topics(), cfg.source_quality_map())
    updated = 0
    for row in rows:
        raw = RawItem(
            source_id=row["source_id"], external_id=row["external_id"], kind=row["kind"],
            title=row["title"] or "", url=row["url"] or "",
            published_at=_parse_dt(row["published_at"]),
            country=row["country"] or "", language=row["language"] or "",
            category=row["category"] or "",
            tags=json.loads(row["tags"] or "[]"),
            payload=json.loads(row["payload_json"] or "{}"),
        )
        item = scorer.score(normalize_item(raw))
        if item.kind in ("article", "hn", "filing"):
            conn.execute(
                """UPDATE articles SET score=?, score_components=?, topics=?
                   WHERE source_id=? AND external_id=?""",
                (item.score, json.dumps(item.score_components),
                 json.dumps(item.topics, ensure_ascii=False),
                 item.source_id, item.external_id))
        elif item.kind == "paper":
            conn.execute("UPDATE papers SET score=?, topics=? WHERE arxiv_id=?",
                         (item.score, json.dumps(item.topics, ensure_ascii=False),
                          item.external_id))
        elif item.kind == "repo":
            conn.execute("UPDATE repositories SET score=? WHERE full_name=?",
                         (item.score, item.external_id))
        elif item.kind == "model":
            conn.execute("UPDATE models SET score=? WHERE hf_id=?",
                         (item.score, item.external_id))
        elif item.kind == "video":
            conn.execute("UPDATE videos SET score=? WHERE video_id=?",
                         (item.score, item.external_id))
        updated += 1

    conn.commit()
    logging.info("rescored %d items", updated)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
