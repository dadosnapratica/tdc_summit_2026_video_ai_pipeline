from __future__ import annotations

import logging
from typing import Any, Dict, List

import requests

from workshop.backend.agents.asset_sources_common import SearchConfig, safe_get

logger = logging.getLogger(__name__)


def search(query: str, cfg: SearchConfig) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    try:
        r = requests.get(
            "https://images-api.nasa.gov/search",
            params={"q": query, "media_type": "image,video"},
            timeout=cfg.timeout_s,
        )
        r.raise_for_status()
        data = r.json()
        items = safe_get(data, ["collection", "items"], []) or []
        for it in items[: cfg.per_source]:
            links = it.get("links", []) or []
            href = links[0].get("href", "") if links else ""
            asset_type = "image"
            data0 = (it.get("data", []) or [{}])[0]
            mt = str(data0.get("media_type", "")).lower()
            if "video" in mt:
                asset_type = "video"
            out.append(
                {
                    "asset_type": asset_type,
                    "url": href or data0.get("nasa_id", ""),
                    "preview_url": href,
                    "source": "nasa",
                    "license": "Public domain (NASA imagery, verify per item)",
                    "author": data0.get("center", "") or data0.get("photographer", ""),
                    "text": data0.get("title", "") or data0.get("description", "") or "",
                }
            )
    except Exception as e:
        logger.warning("[nasa] %s", e)
    return out

