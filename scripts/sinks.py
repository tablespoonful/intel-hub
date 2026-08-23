"""出力先 (Sink)。

- SQLiteSink : ローカル開発用。db/schema.sql をそのまま適用した SQLite に書く。
- WorkerSink : 本番用。Cloudflare Worker の POST /api/ingest へ送る (docs/dev-spec.md §3)。
"""
from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import asdict
from pathlib import Path
from typing import Any, Protocol

import httpx

from collectors.base import RunStats, USER_AGENT
from collectors.markets.providers import Candle, MacroValue
from pipeline.normalize.normalizer import NormalizedItem

logger = logging.getLogger("intel_hub")
ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "db" / "schema.sql"


class Sink(Protocol):
    def write(
        self,
        sources: list[dict[str, Any]],
        items: list[NormalizedItem],
        candles: list[Candle],
        macro_values: list[MacroValue],
        events: list[dict[str, Any]],
        runs: list[RunStats],
    ) -> dict[str, int]: ...


def _iso(dt: Any) -> str | None:
    if dt is None:
        return None
    if hasattr(dt, "strftime"):
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    return str(dt)


class SQLiteSink:
    def __init__(self, db_path: str | Path = "data/intel.db") -> None:
        self.path = Path(db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def write(self, sources, items, candles, macro_values, events, runs) -> dict[str, int]:
        c = self.conn
        counts = {"raw_items": 0, "articles": 0, "papers": 0, "repositories": 0,
                  "models": 0, "videos": 0, "market_prices": 0, "macro_values": 0,
                  "events": 0, "duplicates": 0}

        for s in sources:
            c.execute(
                """INSERT INTO sources (id,name,method,url,country,language,category,quality,tier,enabled)
                   VALUES (?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(id) DO UPDATE SET name=excluded.name, method=excluded.method,
                     url=excluded.url, quality=excluded.quality, tier=excluded.tier,
                     enabled=excluded.enabled, updated_at=datetime('now')""",
                (s["id"], s.get("name", s["id"]), s.get("method", "api"), s.get("url", ""),
                 s.get("country", ""), s.get("language", ""), s.get("category", ""),
                 float(s.get("quality", 0.5)), s.get("tier", "normal"),
                 0 if s.get("enabled") is False else 1),
            )

        for it in items:
            cur = c.execute(
                """INSERT OR IGNORE INTO raw_items
                   (source_id,external_id,kind,url,title,published_at,fetched_at,
                    country,language,category,tags,raw_hash,payload_json)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (it.source_id, it.external_id, it.kind, it.url, it.title,
                 it.published_at, it.fetched_at, it.country, it.language, it.category,
                 json.dumps(it.tags, ensure_ascii=False), it.raw_hash,
                 json.dumps(it.payload, ensure_ascii=False, default=str)),
            )
            if cur.rowcount == 0:
                counts["duplicates"] += 1
            else:
                counts["raw_items"] += 1
            raw_id = c.execute(
                "SELECT id FROM raw_items WHERE source_id=? AND external_id=?",
                (it.source_id, it.external_id)).fetchone()
            raw_item_id = raw_id[0] if raw_id else None
            self._write_typed(it, raw_item_id, counts)

        if candles:
            self._ensure_market_symbols()
        for cd in candles:
            cur = c.execute(
                """INSERT OR IGNORE INTO market_prices
                   (symbol,ts,interval,open,high,low,close,volume,provider)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (cd.symbol, cd.ts, cd.interval, cd.open, cd.high, cd.low, cd.close,
                 cd.volume, cd.provider))
            counts["market_prices"] += cur.rowcount

        for mv in macro_values:
            c.execute(
                """INSERT INTO macro_series (id,name,source,country) VALUES (?,?,?,?)
                   ON CONFLICT(id) DO NOTHING""",
                (mv.series_id, mv.name, mv.source, mv.country))
            cur = c.execute(
                """INSERT INTO macro_values (series_id,date,value,fetched_at)
                   VALUES (?,?,?,datetime('now'))
                   ON CONFLICT(series_id,date) DO UPDATE SET value=excluded.value""",
                (mv.series_id, mv.date, mv.value))
            counts["macro_values"] += 1

        for ev in events:
            cur = c.execute(
                """INSERT INTO events (event_type,title,summary,occurred_at,country,
                     importance,topics,source_count)
                   VALUES (?,?,?,?,?,?,?,?)
                   ON CONFLICT(event_type,title,occurred_at) DO UPDATE SET
                     importance=MAX(events.importance, excluded.importance),
                     source_count=excluded.source_count""",
                (ev["event_type"], ev["title"], ev.get("summary", ""), ev["occurred_at"],
                 ev.get("country", ""), float(ev.get("importance", 0)),
                 json.dumps(ev.get("topics", []), ensure_ascii=False),
                 int(ev.get("source_count", 1))))
            counts["events"] += 1
            event_id = c.execute(
                "SELECT id FROM events WHERE event_type=? AND title=? AND occurred_at=?",
                (ev["event_type"], ev["title"], ev["occurred_at"])).fetchone()
            if event_id:
                for ent in ev.get("entities", []):
                    c.execute(
                        "INSERT OR IGNORE INTO event_entities (event_id,entity_id) VALUES (?,?)",
                        (event_id[0], ent))

        for r in runs:
            c.execute(
                """INSERT INTO collector_runs
                   (collector,started_at,finished_at,status,fetched,inserted,duplicate,failed,error)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (r.collector, _iso(r.started_at), _iso(r.finished_at), r.status,
                 r.fetched, r.inserted, r.duplicate, r.failed, r.error))

        c.commit()
        return counts

    def _ensure_market_symbols(self) -> None:
        from pipeline import config as cfg
        for s in cfg.markets().get("symbols", []):
            self.conn.execute(
                """INSERT INTO market_symbols (canonical,name,asset,country,providers)
                   VALUES (?,?,?,?,?)
                   ON CONFLICT(canonical) DO UPDATE SET providers=excluded.providers""",
                (s["canonical"], s.get("name", s["canonical"]), s.get("asset", "index"),
                 s.get("country", ""), json.dumps(s.get("providers", {}))))

    def _write_typed(self, it: NormalizedItem, raw_item_id: int | None, counts: dict) -> None:
        c = self.conn
        p = it.payload
        if it.kind in ("article", "hn", "filing"):
            c.execute(
                """INSERT INTO articles
                   (raw_item_id,source_id,external_id,url,canonical_url,title,normalized_title,
                    summary,published_at,fetched_at,country,language,category,tags,topics,
                    score,score_components,ai_status)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(source_id,external_id) DO UPDATE SET
                     score=excluded.score, score_components=excluded.score_components,
                     topics=excluded.topics""",
                (raw_item_id, it.source_id, it.external_id, it.url, it.canonical_url,
                 it.title, it.normalized_title, it.summary, it.published_at, it.fetched_at,
                 it.country, it.language, it.category,
                 json.dumps(it.tags, ensure_ascii=False),
                 json.dumps(it.topics, ensure_ascii=False),
                 it.score, json.dumps(it.score_components), it.ai_status))
            counts["articles"] += 1
        elif it.kind == "paper":
            c.execute(
                """INSERT INTO papers (raw_item_id,arxiv_id,url,title,abstract,authors,
                     categories,published_at,updated_at,fetched_at,topics,score,ai_status)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(arxiv_id) DO UPDATE SET score=excluded.score, topics=excluded.topics""",
                (raw_item_id, it.external_id, it.url, it.title,
                 it.summary,
                 json.dumps(p.get("authors", []), ensure_ascii=False),
                 json.dumps(p.get("categories", []), ensure_ascii=False),
                 it.published_at, p.get("updated_at"), it.fetched_at,
                 json.dumps(it.topics, ensure_ascii=False), it.score, it.ai_status))
            counts["papers"] += 1
        elif it.kind == "repo":
            c.execute(
                """INSERT INTO repositories (full_name,url,description,language,topics,
                     latest_release,release_published_at,stars,forks,open_issues,pushed_at,
                     fetched_at,score)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(full_name) DO UPDATE SET
                     stars=excluded.stars, forks=excluded.forks, open_issues=excluded.open_issues,
                     pushed_at=excluded.pushed_at, latest_release=excluded.latest_release,
                     release_published_at=excluded.release_published_at,
                     fetched_at=excluded.fetched_at, score=excluded.score""",
                (it.external_id, it.url, p.get("description", ""), p.get("language", ""),
                 json.dumps(p.get("topics", []), ensure_ascii=False),
                 p.get("latest_release"), p.get("release_published_at"),
                 int(p.get("stars") or 0), int(p.get("forks") or 0),
                 int(p.get("open_issues") or 0), p.get("pushed_at"), it.fetched_at, it.score))
            c.execute(
                """INSERT OR IGNORE INTO repo_snapshots (full_name,snapped_at,stars,forks,open_issues)
                   VALUES (?,?,?,?,?)""",
                (it.external_id, it.fetched_at, int(p.get("stars") or 0),
                 int(p.get("forks") or 0), int(p.get("open_issues") or 0)))
            counts["repositories"] += 1
        elif it.kind == "model":
            c.execute(
                """INSERT INTO models (hf_id,url,author,pipeline_tag,tags,downloads,likes,
                     hf_created_at,hf_updated_at,fetched_at,score)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(hf_id) DO UPDATE SET downloads=excluded.downloads,
                     likes=excluded.likes, hf_updated_at=excluded.hf_updated_at,
                     fetched_at=excluded.fetched_at, score=excluded.score""",
                (it.external_id, it.url, p.get("author", ""), p.get("pipeline_tag", ""),
                 json.dumps(p.get("tags", []), ensure_ascii=False),
                 int(p.get("downloads") or 0), int(p.get("likes") or 0),
                 p.get("createdAt"), it.published_at, it.fetched_at, it.score))
            counts["models"] += 1
        elif it.kind == "video":
            c.execute(
                """INSERT INTO videos (video_id,channel_id,channel_name,url,title,description,
                     published_at,fetched_at,country,score)
                   VALUES (?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(video_id) DO UPDATE SET score=excluded.score""",
                (it.external_id, p.get("channel_id", ""), p.get("channel_name", ""),
                 it.url, it.title, it.summary, it.published_at, it.fetched_at,
                 it.country, it.score))
            counts["videos"] += 1


class WorkerSink:
    def __init__(self, base_url: str, token: str) -> None:
        self.url = base_url.rstrip("/") + "/api/ingest"
        self.token = token

    def write(self, sources, items, candles, macro_values, events, runs) -> dict[str, int]:
        payload = {
            "sources": sources,
            "items": [self._item(i) for i in items],
            "market_prices": [asdict(cd) for cd in candles],
            "macro_values": [asdict(mv) for mv in macro_values],
            "events": events,
            "collector_runs": [
                {"collector": r.collector, "started_at": _iso(r.started_at),
                 "finished_at": _iso(r.finished_at), "status": r.status,
                 "fetched": r.fetched, "inserted": r.inserted,
                 "duplicate": r.duplicate, "failed": r.failed, "error": r.error}
                for r in runs
            ],
        }
        resp = httpx.post(
            self.url, json=payload, timeout=120,
            headers={"Authorization": f"Bearer {self.token}", "User-Agent": USER_AGENT})
        resp.raise_for_status()
        body = resp.json()
        logger.info("worker ingest: %s", body)
        inserted = body.get("inserted", {}) if isinstance(body, dict) else {}
        return {**{k: int(v) for k, v in inserted.items()},
                "duplicates": int(body.get("duplicates", 0))}

    @staticmethod
    def _item(it: NormalizedItem) -> dict[str, Any]:
        d = asdict(it)
        d.pop("dedupe_of", None)
        return d
