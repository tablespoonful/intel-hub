"""YouTube uploads-playlist collector (sources.yaml: youtube). search.list は使用しない."""
from __future__ import annotations

import os
from datetime import datetime, timezone

from dateutil import parser as dateparser

from collectors.base import RawItem, RunStats, get_json, logger

COLLECTOR = "youtube"
API_BASE = "https://www.googleapis.com/youtube/v3"


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


def parse_playlist_item(item: dict, channel_cfg: dict) -> RawItem | None:
    snippet = item.get("snippet", {})
    video_id = snippet.get("resourceId", {}).get("videoId")
    if not video_id:
        return None
    return RawItem(
        source_id="youtube",
        external_id=video_id,
        kind="video",
        title=snippet.get("title", ""),
        url=f"https://www.youtube.com/watch?v={video_id}",
        published_at=_parse_dt(snippet.get("publishedAt")),
        country=channel_cfg.get("country", ""),
        payload={
            "channel_id": channel_cfg.get("id", ""),
            "channel_name": channel_cfg.get("name", ""),
            "description": snippet.get("description", "")[:1000],
        },
    )


def uploads_playlists(channels_json: dict) -> dict[str, str]:
    playlists: dict[str, str] = {}
    for item in channels_json.get("items", []):
        uploads = (
            item.get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads")
        )
        if uploads:
            playlists[item["id"]] = uploads
    return playlists


def collect(config: dict) -> tuple[list[RawItem], RunStats]:
    stats = RunStats(collector=COLLECTOR)
    api_key = os.environ.get("YOUTUBE_API_KEY")
    if not api_key:
        stats.error = "skipped: no API key"
        return [], stats.finish("success")

    channels = config.get("channels", [])
    max_videos = config.get("max_videos_per_channel", 10)
    channel_ids = [c["id"] for c in channels]
    playlists: dict[str, str] = {}
    try:
        for start in range(0, len(channel_ids), 50):
            batch = channel_ids[start : start + 50]
            channels_json = get_json(
                f"{API_BASE}/channels",
                params={
                    "part": "contentDetails",
                    "id": ",".join(batch),
                    "key": api_key,
                },
            )
            playlists.update(uploads_playlists(channels_json))
    except Exception as exc:
        stats.error = f"youtube channels fetch failed: {exc}"
        return [], stats.finish("failed")

    items: list[RawItem] = []
    for channel in channels:
        playlist_id = playlists.get(channel["id"])
        if not playlist_id:
            stats.failed += 1
            logger.warning("youtube: no uploads playlist for %s", channel.get("name"))
            continue
        try:
            playlist_json = get_json(
                f"{API_BASE}/playlistItems",
                params={
                    "part": "snippet",
                    "playlistId": playlist_id,
                    "maxResults": max_videos,
                    "key": api_key,
                },
            )
        except Exception as exc:
            stats.failed += 1
            logger.warning("youtube: playlist %s failed: %s", playlist_id, exc)
            continue
        for entry in playlist_json.get("items", []):
            item = parse_playlist_item(entry, channel)
            if item is None:
                continue
            items.append(item)
            stats.fetched += 1
    return items, stats.finish()
