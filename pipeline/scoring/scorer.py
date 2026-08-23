"""ルールベーススコアリング (AI 前段フィルタ)。

score = 100 * Σ(weight_i * component_i) / Σ(weight_i) - penalties, 0-100 に clamp。
成分はすべて 0-1。重み・飽和値・閾値は config/scoring.yaml から。
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

from pipeline.normalize.normalizer import NormalizedItem


def _log_norm(value: float, saturation: float) -> float:
    if value <= 0 or saturation <= 0:
        return 0.0
    return min(1.0, math.log10(1 + value) / math.log10(1 + saturation))


class Scorer:
    def __init__(
        self,
        scoring_cfg: dict[str, Any],
        topics_cfg: dict[str, Any],
        quality_map: dict[str, float],
        now: datetime | None = None,
    ) -> None:
        self.weights: dict[str, float] = dict(scoring_cfg.get("weights", {}))
        self.half_life = float(scoring_cfg.get("recency", {}).get("half_life_hours", 24))
        self.pop_sat: dict[str, float] = dict(scoring_cfg.get("popularity", {}).get("saturation", {}))
        self.vel_sat: dict[str, float] = dict(scoring_cfg.get("velocity", {}).get("saturation", {}))
        self.ai_threshold = float(scoring_cfg.get("ai_threshold", 65))
        self.neg_penalty = float(scoring_cfg.get("negative_keyword_penalty", 15))
        self.topics: dict[str, dict[str, Any]] = topics_cfg.get("topics", {})
        self.negative_keywords: list[str] = [k.lower() for k in topics_cfg.get("negative_keywords", [])]
        self.quality_map = quality_map
        self.now = now or datetime.now(timezone.utc)

    # ---- components ----

    def recency(self, item: NormalizedItem) -> float:
        ts = item.published_at or item.fetched_at
        if not ts:
            return 0.0
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except ValueError:
            return 0.0
        age_h = max(0.0, (self.now - dt).total_seconds() / 3600)
        return math.exp(-math.log(2) * age_h / self.half_life)

    def source_quality(self, item: NormalizedItem) -> float:
        return float(self.quality_map.get(item.source_id, 0.5))

    def relevance(self, item: NormalizedItem) -> tuple[float, list[str]]:
        text = f"{item.title} {item.summary}".lower()
        matched: list[str] = []
        best = 0.0
        for topic_id, cfg in self.topics.items():
            weight = float(cfg.get("weight", 0.5))
            if any(kw.lower() in text for kw in cfg.get("keywords", [])):
                matched.append(topic_id)
                best = max(best, weight)
        # 複数トピック該当は関心領域の交差 (例: robotics x llm) としてボーナス
        bonus = min(0.15, 0.05 * max(0, len(matched) - 1))
        return (min(1.0, best + bonus), matched)

    def popularity(self, item: NormalizedItem) -> float:
        p = item.payload
        if item.kind == "hn":
            return _log_norm(float(p.get("points") or 0), self.pop_sat.get("hn_points", 500))
        if item.kind == "repo":
            return _log_norm(float(p.get("stars") or 0), self.pop_sat.get("stars", 20000))
        if item.kind == "model":
            dl = _log_norm(float(p.get("downloads") or 0), self.pop_sat.get("hf_downloads", 1_000_000))
            likes = _log_norm(float(p.get("likes") or 0), self.pop_sat.get("hf_likes", 2000))
            return max(dl, likes)
        if item.kind == "video":
            return _log_norm(float(p.get("views") or 0), self.pop_sat.get("youtube_views", 500_000))
        return 0.0

    def velocity(self, item: NormalizedItem) -> float:
        p = item.payload
        d24 = p.get("stars_24h_delta")
        d7 = p.get("stars_7d_delta")
        v = 0.0
        if d24 is not None:
            v = max(v, _log_norm(float(d24), self.vel_sat.get("stars_24h_delta", 300)))
        if d7 is not None:
            v = max(v, _log_norm(float(d7), self.vel_sat.get("stars_7d_delta", 1500)))
        return v

    def novelty(self, item: NormalizedItem) -> float:
        """MVP: 履歴 DB を持たないため簡易判定。

        - 新規性の高い kind (paper, filing) は published が新しければ 1.0
        - model/repo は作成日が新しいものを新規、既存の更新は 0.5
        """
        p = item.payload
        created = p.get("createdAt") or p.get("created_at") or p.get("hf_created_at")
        if item.kind in ("model", "repo") and created:
            try:
                dt = datetime.fromisoformat(str(created).replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                age_days = (self.now - dt).total_seconds() / 86400
                return 1.0 if age_days <= 7 else 0.5
            except ValueError:
                return 0.5
        return 1.0 if item.published_at else 0.5

    # ---- main ----

    def score(self, item: NormalizedItem) -> NormalizedItem:
        rel, matched_topics = self.relevance(item)
        components = {
            "recency": self.recency(item),
            "source_quality": self.source_quality(item),
            "relevance": rel,
            "velocity": self.velocity(item),
            "popularity": self.popularity(item),
            "novelty": self.novelty(item),
        }
        total_w = sum(self.weights.values()) or 1.0
        raw = sum(self.weights.get(k, 0) * v for k, v in components.items()) / total_w
        score = raw * 100

        text = f"{item.title} {item.summary}".lower()
        if any(kw in text for kw in self.negative_keywords):
            score -= self.neg_penalty

        item.score = round(max(0.0, min(100.0, score)), 2)
        item.score_components = {k: round(v, 4) for k, v in components.items()}
        item.topics = matched_topics
        item.ai_status = "pending" if item.score >= self.ai_threshold else "none"
        return item

    def score_batch(self, items: list[NormalizedItem]) -> list[NormalizedItem]:
        return [self.score(i) for i in items]
