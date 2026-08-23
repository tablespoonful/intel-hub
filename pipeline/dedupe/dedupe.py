"""バッチ内重複排除。

判定順:
 1. (source_id, external_id) 完全一致
 2. raw_hash 一致
 3. canonical_url 一致 (空以外)
 4. normalized_title の類似度 >= threshold (同一 kind 内)

クロスラン (過去データとの) 重複は D1 の UNIQUE 制約 (INSERT OR IGNORE) が担う。
embedding は使わない (MVP 方針)。
"""
from __future__ import annotations

from difflib import SequenceMatcher

from pipeline.normalize.normalizer import NormalizedItem

TITLE_SIMILARITY_THRESHOLD = 0.92


def title_similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def _key(item: NormalizedItem) -> str:
    return f"{item.source_id}:{item.external_id}"


def dedupe_batch(
    items: list[NormalizedItem],
    quality: dict[str, float] | None = None,
    threshold: float = TITLE_SIMILARITY_THRESHOLD,
) -> tuple[list[NormalizedItem], list[NormalizedItem]]:
    """(unique, duplicates) を返す。

    重複グループでは source quality が最も高いものを代表にする。
    duplicates 側は dedupe_of に代表キーを持つ。
    """
    quality = quality or {}
    ranked = sorted(
        items,
        key=lambda i: (quality.get(i.source_id, 0.5), i.published_at or ""),
        reverse=True,
    )

    unique: list[NormalizedItem] = []
    duplicates: list[NormalizedItem] = []
    seen_ids: dict[str, NormalizedItem] = {}
    seen_hashes: dict[str, NormalizedItem] = {}
    seen_urls: dict[str, NormalizedItem] = {}

    for item in ranked:
        rep = (
            seen_ids.get(_key(item))
            or seen_hashes.get(item.raw_hash)
            or (seen_urls.get(item.canonical_url) if item.canonical_url else None)
        )
        if rep is None and item.normalized_title:
            for u in unique:
                if u.kind != item.kind or not u.normalized_title:
                    continue
                # 長さが大きく違うものは比較しない (高速化)
                if abs(len(u.normalized_title) - len(item.normalized_title)) > 24:
                    continue
                if title_similarity(u.normalized_title, item.normalized_title) >= threshold:
                    rep = u
                    break

        if rep is not None:
            item.dedupe_of = _key(rep)
            duplicates.append(item)
            continue

        unique.append(item)
        seen_ids[_key(item)] = item
        seen_hashes[item.raw_hash] = item
        if item.canonical_url:
            seen_urls[item.canonical_url] = item

    order = {_key(i): n for n, i in enumerate(items)}
    unique.sort(key=lambda i: order.get(_key(i), 0))
    return unique, duplicates
