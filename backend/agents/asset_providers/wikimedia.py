from __future__ import annotations

import logging
import re
from typing import Any, Dict, List

import requests

from workshop.backend.agents.asset_sources_common import SearchConfig, safe_get

logger = logging.getLogger(__name__)


def search(query: str, cfg: SearchConfig) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    try:
        r = requests.get(
            "https://commons.wikimedia.org/w/api.php",
            params={
                "action": "query",
                "format": "json",
                "list": "search",
                "srsearch": f"filetype:bitmap|drawing {query}",
                "srlimit": cfg.per_source,
                "srnamespace": 6,
            },
            timeout=cfg.timeout_s,
        )
        r.raise_for_status()
        data = r.json()
        hits = safe_get(data, ["query", "search"], []) or []
        titles = [h.get("title") for h in hits if h.get("title")]
        if not titles:
            return out

        r = requests.get(
            "https://commons.wikimedia.org/w/api.php",
            params={
                "action": "query",
                "format": "json",
                "prop": "imageinfo",
                "iiprop": "url|extmetadata",
                "titles": "|".join(titles),
            },
            timeout=cfg.timeout_s,
        )
        r.raise_for_status()
        data = r.json()
        pages = safe_get(data, ["query", "pages"], {}) or {}
        for _, page in pages.items():
            iis = page.get("imageinfo", []) or []
            if not iis:
                continue
            ii = iis[0]
            url = ii.get("url", "")
            meta = ii.get("extmetadata", {}) or {}
            license_short = safe_get(meta, ["LicenseShortName", "value"], "")
            artist = safe_get(meta, ["Artist", "value"], "")
            title = page.get("title", "")
            page_url = f"https://commons.wikimedia.org/wiki/{title.replace(' ', '_')}" if title else ""
            out.append(
                {
                    "asset_type": "image",
                    "url": page_url or url,
                    "preview_url": url,
                    "source": "wikimedia",
                    "license": license_short or "Creative Commons (verify per item)",
                    "author": re.sub(r"<.*?>", "", str(artist)) if artist else "",
                    "text": "",
                }
            )
    except Exception as e:
        logger.warning("[wikimedia] %s", e)
    return out

