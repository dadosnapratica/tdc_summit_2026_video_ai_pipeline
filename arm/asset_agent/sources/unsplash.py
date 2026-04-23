from __future__ import annotations

import logging
import os
from typing import Any, Dict, List

import requests

from ..common import SearchConfig

logger = logging.getLogger(__name__)


def search(query: str, cfg: SearchConfig) -> List[Dict[str, Any]]:
    key = (os.getenv("UNSPLASH_ACCESS_KEY") or "").strip()
    if not key:
        return []

    out: List[Dict[str, Any]] = []
    try:
        r = requests.get(
            "https://api.unsplash.com/search/photos",
            headers={"Authorization": f"Client-ID {key}"},
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
                    "attribution_url": it.get("links", {}).get("html", ""),
                    "query": query,
                    "width": it.get("width"),
                    "height": it.get("height"),
                }
            )
    except Exception as e:
        logger.warning("[unsplash] search falhou: %s", e)

    return out

