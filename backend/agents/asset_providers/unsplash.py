from __future__ import annotations

import logging
import os
from typing import Any, Dict, List

import requests

from workshop.backend.agents.asset_sources_common import SearchConfig

logger = logging.getLogger(__name__)


def search(query: str, cfg: SearchConfig) -> List[Dict[str, Any]]:
    key = (os.getenv("UNSPLASH_ACCESS_KEY") or "").strip()
    proxy_base = (os.getenv("LAB_CREDENTIALS_BASE_URL") or "").strip().rstrip("/")
    proxy_token = (os.getenv("WORKSHOP_ACCESS_TOKEN") or "").strip()
    use_proxy = bool(proxy_base and proxy_token)
    if not key and not use_proxy:
        return []

    out: List[Dict[str, Any]] = []
    try:
        r = requests.get(
            f"{proxy_base}/v1/proxy/unsplash/search/photos" if use_proxy else "https://api.unsplash.com/search/photos",
            headers=({"Authorization": f"Bearer {proxy_token}"} if use_proxy else {"Authorization": f"Client-ID {key}"}),
            params={"query": query, "per_page": cfg.per_source},
            timeout=cfg.timeout_s,
        )
        r.raise_for_status()
        data = r.json()
        for it in (data.get("results", []) or [])[: cfg.per_source]:
            out.append(
                {
                    "asset_type": "image",
                    "url": it.get("links", {}).get("html", ""),
                    "preview_url": it.get("urls", {}).get("regular", ""),
                    "source": "unsplash",
                    "license": "Unsplash License (free to use)",
                    "author": (it.get("user", {}) or {}).get("name", "") or "",
                    "text": it.get("alt_description", "") or it.get("description", "") or "",
                    "width": it.get("width"),
                    "height": it.get("height"),
                }
            )
    except Exception as e:
        logger.warning("[unsplash] %s", e)
    return out

