"""Cliente YouTube Data API v3 — busca por tópico (sem depender de workshop/)."""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def _snippet_description(item: dict) -> str:
    sn = item.get("snippet") or {}
    d = (sn.get("description") or "").strip()
    if d:
        return d
    loc = sn.get("localized")
    if isinstance(loc, dict):
        d = (loc.get("description") or "").strip()
        if d:
            return d
    return ""


def get_videos_by_topic(
    topic: str,
    *,
    category_id: str = "28",
    region: str = "BR",
    n: int = 25,
    relevance_language: str = "pt",
    strict_language: bool = False,
) -> List[Dict[str, Any]]:
    import requests

    proxy_base = (os.getenv("LAB_CREDENTIALS_BASE_URL") or "").strip().rstrip("/")
    proxy_token = (os.getenv("WORKSHOP_ACCESS_TOKEN") or "").strip()
    use_proxy = bool(proxy_base and proxy_token)

    key = (os.getenv("YOUTUBE_API_KEY") or "").strip()
    if not key and not use_proxy:
        logger.warning("[youtube_client] YOUTUBE_API_KEY ausente e proxy não configurado")
        return []

    def _yt_get(path: str, *, params: Dict[str, Any]) -> Dict[str, Any]:
        if use_proxy:
            # Mesmo em modo proxy, permitir enviar `key` (workshop/testes) caso esteja definido localmente.
            # Isso evita 403 "unregistered callers" quando o jwt_broker não tem YOUTUBE_API_KEY configurado.
            if key and "key" not in params:
                params = {**params, "key": key}
            r = requests.get(
                f"{proxy_base}/v1/proxy/youtube/{path.lstrip('/')}",
                params=params,
                headers={"Authorization": f"Bearer {proxy_token}"},
                timeout=20,
            )
            r.raise_for_status()
            return r.json()
        r = requests.get(
            f"https://www.googleapis.com/youtube/v3/{path.lstrip('/')}",
            params={**params, "key": key},
            timeout=20,
        )
        r.raise_for_status()
        return r.json()

    search_response = _yt_get(
        "search",
        params={
            "part": "snippet",
            "q": topic,
            "type": "video",
            "regionCode": region,
            "relevanceLanguage": relevance_language,
            "videoCategoryId": category_id,
            "maxResults": n,
            "order": "viewCount",
            "safeSearch": "none",
        },
    )

    video_ids = [
        item["id"]["videoId"]
        for item in search_response.get("items", [])
        if item.get("id", {}).get("videoId")
    ]
    if not video_ids:
        return []

    _hl = (relevance_language or "pt").strip().split("-")[0].lower()
    if len(_hl) != 2:
        _hl = "pt"
    videos_response = _yt_get(
        "videos",
        params={
            "part": "snippet,statistics",
            "id": ",".join(video_ids),
            "maxResults": min(50, len(video_ids)),
            "hl": _hl,
        },
    )

    items = videos_response.get("items", [])
    if strict_language:

        def _is_lang_ok(it: dict) -> bool:
            sn = it.get("snippet", {}) or {}
            dl = (sn.get("defaultLanguage") or "").lower()
            dal = (sn.get("defaultAudioLanguage") or "").lower()
            return dl.startswith(relevance_language.lower()) or dal.startswith(relevance_language.lower())

        items = [it for it in items if _is_lang_ok(it)]

    out: List[Dict[str, Any]] = []
    for item in items:
        out.append(
            {
                "video_id": item.get("id", ""),
                "video_url": f"https://www.youtube.com/watch?v={item.get('id', '')}" if item.get("id") else "",
                "title": item["snippet"]["title"],
                "description": _snippet_description(item),
                "views": item.get("statistics", {}).get("viewCount", "0"),
                "channel_id": item.get("snippet", {}).get("channelId", ""),
                "channel_url": f"https://www.youtube.com/channel/{item.get('snippet', {}).get('channelId', '')}"
                if item.get("snippet", {}).get("channelId")
                else "",
                "channel": item["snippet"]["channelTitle"],
                "published": item["snippet"]["publishedAt"],
            }
        )
    return out
