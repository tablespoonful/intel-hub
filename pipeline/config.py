"""YAML 設定ローダ。"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"


@lru_cache(maxsize=None)
def _load(name: str) -> dict[str, Any]:
    path = CONFIG_DIR / name
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def sources() -> dict[str, Any]:
    return _load("sources.yaml")


def topics() -> dict[str, Any]:
    return _load("topics.yaml")


def entities() -> list[dict[str, Any]]:
    return _load("entities.yaml").get("entities", [])


def markets() -> dict[str, Any]:
    return _load("markets.yaml")


def scoring() -> dict[str, Any]:
    return _load("scoring.yaml")


def source_quality_map() -> dict[str, float]:
    """source_id -> quality。RSS 以外の組み込み collector にも既定値を与える。"""
    m: dict[str, float] = {
        "hackernews": 0.6,
        "huggingface": 0.7,
        "arxiv": 0.75,
        "github": 0.75,
        "youtube": 0.6,
        "sec-edgar": 0.9,
    }
    cfg = sources()
    for s in cfg.get("rss", []):
        m[s["id"]] = float(s.get("quality", 0.5))
    macro = cfg.get("macro", {})
    for group in ("boj", "fed"):
        for s in macro.get(group, []):
            m[s["id"]] = float(s.get("quality", 0.9))
    return m
