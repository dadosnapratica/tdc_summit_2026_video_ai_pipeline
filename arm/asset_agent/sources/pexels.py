from __future__ import annotations

import logging
import os
from typing import Any, Dict, List

import requests

from ..common import SearchConfig, safe_get

logger = logging.getLogger(__name__)


def search(query: str, cfg: SearchConfig) -> List[Dict[str, Any]]:
    key = (os.getenv("PEXELS_API_KEY") or "").strip()
    if not key:
        return []

    headers = {"Authorization": key}
    out: List[Dict[str, Any]] = []

    # Photos
    try:
        r = requests.get(
            "https://api.pexels.com/v1/search",
            headers=headers,
            params={"query": query, "per_page": cfg.per_source},
            timeout=cfg.timeout_s,
        )
        r.raise_for_status()
        data = r.json()
        for p in data.get("photos", [])[: cfg.per_source]:
            out.append(
                {
                    "asset_type": "image",
                    "url": p.get("url", ""),
                    "preview_url": safe_get(p, ["src", "large"], ""),
                    "source": "pexels",
                    "license": "Pexels License (free to use)",
                    "author": safe_get(p, ["photographer"], ""),
                    "text": p.get("alt", "") or "",
                    "attribution_url": p.get("url", ""),
                    "query": query,
                    "width": p.get("width"),
                    "height": p.get("height"),
                }
            )
    except Exception as e:
        logger.warning("[pexels] photos search falhou: %s", e)

    # Videos
    try:
        r = requests.get(
            "https://api.pexels.com/videos/search",
            headers=headers,
            params={"query": query, "per_page": cfg.per_source},
            timeout=cfg.timeout_s,
        )
        r.raise_for_status()
        data = r.json()
        for v in data.get("videos", [])[: cfg.per_source]:
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
                    "attribution_url": v.get("url", ""),
                    "query": query,
                    "width": vw,
                    "height": vh,
                }
            )
    except Exception as e:
        logger.warning("[pexels] videos search falhou: %s", e)

    return out

