"""Collector 共通基盤: RawItem, HTTP ユーティリティ, 実行結果統計."""
from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import httpx

logger = logging.getLogger("intel_hub")

USER_AGENT = "intel-hub/0.1 (personal research aggregator)"
DEFAULT_TIMEOUT = 20.0
RETRIES = 2


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def compute_hash(*parts: str) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update((p or "").encode("utf-8", errors="replace"))
        h.update(b"\x00")
    return h.hexdigest()


@dataclass
class RawItem:
    source_id: str
    external_id: str
    kind: str                      # article | paper | repo | model | video | hn | filing
    title: str = ""
    url: str = ""
    published_at: datetime | None = None
    fetched_at: datetime = field(default_factory=utcnow)
    country: str = ""
    language: str = ""
    category: str = ""
    tags: list[str] = field(default_factory=list)
    payload: dict[str, Any] = field(default_factory=dict)

    @property
    def raw_hash(self) -> str:
        return compute_hash(self.source_id, self.external_id, self.title, self.url)


@dataclass
class RunStats:
    collector: str
    started_at: datetime = field(default_factory=utcnow)
    finished_at: datetime | None = None
    status: str = "running"        # running | success | partial | failed
    fetched: int = 0
    inserted: int = 0
    duplicate: int = 0
    failed: int = 0
    error: str = ""

    def finish(self, status: str | None = None) -> "RunStats":
        self.finished_at = utcnow()
        if status:
            self.status = status
        elif self.failed and self.fetched:
            self.status = "partial"
        elif self.failed and not self.fetched:
            self.status = "failed"
        else:
            self.status = "success"
        return self


class HttpError(Exception):
    pass


def _request(url: str, headers: dict | None = None, params: dict | None = None) -> httpx.Response:
    hdrs = {"User-Agent": USER_AGENT}
    if headers:
        hdrs.update(headers)
    last_exc: Exception | None = None
    for attempt in range(RETRIES + 1):
        try:
            resp = httpx.get(url, headers=hdrs, params=params,
                             timeout=DEFAULT_TIMEOUT, follow_redirects=True)
            if resp.status_code == 429 and attempt < RETRIES:
                time.sleep(2 * (attempt + 1))
                continue
            resp.raise_for_status()
            return resp
        except (httpx.HTTPError, httpx.HTTPStatusError) as exc:  # noqa: PERF203
            last_exc = exc
            if attempt < RETRIES:
                time.sleep(1.5 * (attempt + 1))
    raise HttpError(f"GET {url} failed: {last_exc}") from last_exc


def get_text(url: str, headers: dict | None = None, params: dict | None = None) -> str:
    return _request(url, headers, params).text


def get_json(url: str, headers: dict | None = None, params: dict | None = None) -> Any:
    return _request(url, headers, params).json()


def dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, default=str)
