"""YouTube Data API v3 (lab) — suporta API key local ou proxy JWT broker."""

from __future__ import annotations

import os
from typing import Any, Dict, List

import requests


def _snippet_description(item: dict) -> str:
    """Texto da descrição do vídeo (snippet ou localized)."""
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


def _proxy_cfg() -> tuple[bool, str, Dict[str, str]]:
    proxy_base = (os.getenv("LAB_CREDENTIALS_BASE_URL") or "").strip().rstrip("/")
    token = (os.getenv("WORKSHOP_ACCESS_TOKEN") or "").strip()
    use = bool(proxy_base and token)
    headers = {"Authorization": f"Bearer {token}"} if use else {}
    return use, proxy_base, headers


def _yt_get(path: str, *, params: Dict[str, Any]) -> Dict[str, Any]:
    use_proxy, proxy_base, headers = _proxy_cfg()
    key = (os.getenv("YOUTUBE_API_KEY") or "").strip()

    if use_proxy:
        url = f"{proxy_base}/v1/proxy/youtube/{path.lstrip('/')}"
        # Mesmo em modo proxy, permitir enviar `key` (workshop/testes) caso esteja definido localmente.
        # Isso evita 403 "unregistered callers" quando o jwt_broker não tem YOUTUBE_API_KEY configurado.
        if key and "key" not in params:
            params = {**params, "key": key}
        r = requests.get(url, params=params, headers=headers, timeout=20)
        r.raise_for_status()
        return r.json()

    if not key:
        raise RuntimeError("YOUTUBE_API_KEY ausente e proxy não configurado (LAB_CREDENTIALS_BASE_URL + WORKSHOP_ACCESS_TOKEN)")
    url = f"https://www.googleapis.com/youtube/v3/{path.lstrip('/')}"
    r = requests.get(url, params={**params, "key": key}, timeout=20)
    r.raise_for_status()
    return r.json()


def get_trending_videos(category_id: str = "28", region: str = "BR", n: int = 100):
    response = _yt_get(
        "videos",
        params={
            "part": "snippet,statistics",
            "chart": "mostPopular",
            "regionCode": region,
            "videoCategoryId": category_id,
            "maxResults": n,
        },
    )

    return [{
        "video_id": item.get("id", ""),
        "video_url": f"https://www.youtube.com/watch?v={item.get('id', '')}" if item.get("id") else "",
        "title": item["snippet"]["title"],
        "description": _snippet_description(item),
        "views": item.get("statistics", {}).get("viewCount", "0"),
        "channel_id": item["snippet"].get("channelId", ""),
        "channel_url": f"https://www.youtube.com/channel/{item['snippet'].get('channelId', '')}"
        if item["snippet"].get("channelId")
        else "",
        "channel": item["snippet"]["channelTitle"],
        "published": item["snippet"]["publishedAt"],
    } for item in response.get("items", [])]


def get_videos_by_topic(
    topic: str,
    category_id: str = "28",
    region: str = "BR",
    n: int = 25,
    relevance_language: str = "pt",
    strict_language: bool = False,
):
    """
    Busca vídeos por assunto usando o endpoint `search`, e então enriquece com `statistics`.
    Útil para nichos como "astronomia", "IA", etc.
    """
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

    return [{
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
        "lang": item.get("snippet", {}).get("defaultAudioLanguage") or item.get("snippet", {}).get("defaultLanguage") or "",
    } for item in items]


if __name__ == '__main__':
    topic = os.getenv("TOPIC", "").strip()
    relevance_language = os.getenv("RELEVANCE_LANGUAGE", "pt").strip() or "pt"
    strict_language = os.getenv("STRICT_LANGUAGE", "0").strip() in ("1", "true", "True", "yes", "YES")
    trending_videos = (
        get_videos_by_topic(
            topic,
            relevance_language=relevance_language,
            strict_language=strict_language,
        )
        if topic
        else get_trending_videos()
    )
    for idx, video in enumerate(trending_videos, start=1):
        print(
            f"{idx}. {video['title']} - {video['views']} views - "
            f"{video['channel']} - Published on {video['published']}\n"
            f"   Video:  {video.get('video_url', '')}\n"
            f"   Canal:  {video.get('channel_url', '')}\n"
        )
