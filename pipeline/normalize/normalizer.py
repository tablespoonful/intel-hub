"""RawItem -> NormalizedItem 変換。

- タイトルの空白/HTMLエンティティ正規化
- canonical URL (トラッキングパラメータ除去)
- timestamp を ISO8601 UTC 文字列へ
- 言語推定 (日本語/中国語文字の簡易判定)
"""
from __future__ import annotations

import html
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from collectors.base import RawItem

_TRACKING_PARAMS = re.compile(
    r"^(utm_\w*|fbclid|gclid|mc_cid|mc_eid|ref_src|cmpid|igshid|source)$", re.I
)
_WS = re.compile(r"\s+")
_TAG = re.compile(r"<[^>]+>")

_HIRAGANA_KATAKANA = re.compile(r"[぀-ヿ]")
_CJK = re.compile(r"[一-鿿]")


@dataclass
class NormalizedItem:
    source_id: str
    external_id: str
    kind: str
    url: str
    canonical_url: str
    title: str
    normalized_title: str
    summary: str
    published_at: str | None
    fetched_at: str
    country: str
    language: str
    category: str
    tags: list[str]
    raw_hash: str
    payload: dict[str, Any] = field(default_factory=dict)
    topics: list[str] = field(default_factory=list)
    score: float = 0.0
    score_components: dict[str, float] = field(default_factory=dict)
    ai_status: str = "none"
    dedupe_of: str | None = None    # 重複時: 代表アイテムの "source_id:external_id"


def to_utc_iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def canonical_url(url: str) -> str:
    if not url:
        return ""
    parts = urlsplit(url.strip())
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
             if not _TRACKING_PARAMS.match(k)]
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path,
                       urlencode(query), ""))


def clean_text(text: str) -> str:
    text = _TAG.sub(" ", html.unescape(text or ""))
    return _WS.sub(" ", text).strip()


def normalize_title(title: str) -> str:
    """dedupe 比較用: NFKC 小文字化 + 記号除去。"""
    t = unicodedata.normalize("NFKC", clean_text(title)).lower()
    t = re.sub(r"[^\w\s぀-ヿ一-鿿]", " ", t)
    return _WS.sub(" ", t).strip()


def detect_language(text: str, default: str = "en") -> str:
    if not text:
        return default
    if _HIRAGANA_KATAKANA.search(text):
        return "ja"
    if _CJK.search(text):
        return "zh"
    return default


def normalize_item(raw: RawItem) -> NormalizedItem:
    title = clean_text(raw.title)
    summary = clean_text(str(raw.payload.get("summary") or raw.payload.get("abstract")
                             or raw.payload.get("description") or ""))[:3000]
    lang = raw.language or detect_language(title + " " + summary)
    return NormalizedItem(
        source_id=raw.source_id,
        external_id=raw.external_id,
        kind=raw.kind,
        url=raw.url or "",
        canonical_url=canonical_url(raw.url or ""),
        title=title,
        normalized_title=normalize_title(title),
        summary=summary,
        published_at=to_utc_iso(raw.published_at),
        fetched_at=to_utc_iso(raw.fetched_at) or "",
        country=raw.country or "",
        language=lang,
        category=raw.category or "",
        tags=list(raw.tags or []),
        raw_hash=raw.raw_hash,
        payload=dict(raw.payload or {}),
    )
