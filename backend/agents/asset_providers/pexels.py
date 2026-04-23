from __future__ import annotations

import logging
import os
from typing import Any, Dict, List

import requests

from workshop.backend.agents.asset_sources_common import SearchConfig, safe_get

logger = logging.getLogger(__name__)


def search(query: str, cfg: SearchConfig) -> List[Dict[str, Any]]:
    key = (os.getenv("PEXELS_API_KEY") or "").strip()
    proxy_base = (os.getenv("LAB_CREDENTIALS_BASE_URL") or "").strip().rstrip("/")
    proxy_token = (os.getenv("WORKSHOP_ACCESS_TOKEN") or "").strip()
    use_proxy = bool(proxy_base and proxy_token)
    if not key and not use_proxy:
        return []

    headers = {"Authorization": key} if key else {}
    if use_proxy:
        headers = {"Authorization": f"Bearer {proxy_token}"}
    out: List[Dict[str, Any]] = []

    # Photos
    try:
        r = requests.get(
            f"{proxy_base}/v1/proxy/pexels/v1/search" if use_proxy else "https://api.pexels.com/v1/search",
            headers=headers,
            params={"query": query, "per_page": cfg.per_source},
            timeout=cfg.timeout_s,
        )
        r.raise_for_status()
        data = r.json()
        for p in (data.get("photos", []) or [])[: cfg.per_source]:
            out.append(
                {
                    "asset_type": "image",
                    "url": p.get("url", ""),
                    "preview_url": safe_get(p, ["src", "large"], ""),
                    "source": "pexels",
                    "license": "Pexels License (free to use)",
                    "author": safe_get(p, ["photographer"], ""),
                    "text": p.get("alt", "") or "",
                    "width": p.get("width"),
                    "height": p.get("height"),
                }
            )
    except Exception as e:
        logger.warning("[pexels] photos: %s", e)

    # Videos
    try:
        r = requests.get(
            f"{proxy_base}/v1/proxy/pexels/videos/search" if use_proxy else "https://api.pexels.com/videos/search",
            headers=headers,
            params={"query": query, "per_page": cfg.per_source},
            timeout=cfg.timeout_s,
        )
        r.raise_for_status()
        data = r.json()
        for v in (data.get("videos", []) or [])[: cfg.per_source]:
            video_files = v.get("video_files", []) or []
            file_url = video_files[0].get("link", "") if video_files else ""
            vw = v.get("width")
            vh = v.get("height")
            if (vw is None or vh is None) and video_files:
                vw = video_files[0].get("width", vw)
                vh = video_files[0].get("height", vh)
            out.append(
                {
                    "asset_type": "video",
                    "url": file_url or v.get("url", ""),
                    "preview_url": v.get("image", ""),
                    "source": "pexels",
                    "license": "Pexels License (free to use)",
                    "author": safe_get(v, ["user", "name"], ""),
                    "text": v.get("url", "") or "",
                    "width": vw,
                    "height": vh,
                }
            )
    except Exception as e:
        logger.warning("[pexels] videos: %s", e)

    return out

