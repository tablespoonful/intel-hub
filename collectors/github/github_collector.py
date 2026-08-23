"""GitHub repository watch collector (sources.yaml: github)."""
from __future__ import annotations

import os
from datetime import datetime, timezone

from dateutil import parser as dateparser

from collectors.base import RawItem, RunStats, get_json, logger

COLLECTOR = "github"
API_BASE = "https://api.github.com"


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = dateparser.isoparse(value)
    except (ValueError, TypeError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def parse_repo(repo_json: dict, release_json: dict | None) -> RawItem:
    full_name = repo_json.get("full_name", "")
    release = release_json or {}
    return RawItem(
        source_id="github",
        external_id=full_name,
        kind="repo",
        title=full_name,
        url=repo_json.get("html_url", f"https://github.com/{full_name}"),
        published_at=_parse_dt(repo_json.get("pushed_at")),
        payload={
            "stars": repo_json.get("stargazers_count", 0),
            "forks": repo_json.get("forks_count", 0),
            "open_issues": repo_json.get("open_issues_count", 0),
            "pushed_at": repo_json.get("pushed_at", ""),
            "description": repo_json.get("description") or "",
            "language": repo_json.get("language") or "",
            "topics": repo_json.get("topics", []),
            "latest_release": release.get("tag_name", ""),
            "release_published_at": release.get("published_at", ""),
        },
    )


def collect(config: dict) -> tuple[list[RawItem], RunStats]:
    stats = RunStats(collector=COLLECTOR)
    items: list[RawItem] = []
    headers: dict[str, str] | None = None
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers = {"Authorization": f"Bearer {token}"}
    for full_name in config.get("repos", []):
        try:
            repo_json = get_json(f"{API_BASE}/repos/{full_name}", headers=headers)
        except Exception as exc:
            stats.failed += 1
            logger.warning("github: repo %s failed: %s", full_name, exc)
            continue
        release_json: dict | None = None
        try:
            release_json = get_json(
                f"{API_BASE}/repos/{full_name}/releases/latest", headers=headers
            )
        except Exception:
            release_json = None
        items.append(parse_repo(repo_json, release_json))
        stats.fetched += 1
    return items, stats.finish()
