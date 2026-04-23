from __future__ import annotations

import logging
import os
import re
from typing import Any, Dict, List

from workshop.backend.agents.asset_providers._http import get_with_retry
from workshop.backend.agents.asset_sources_common import SearchConfig

logger = logging.getLogger(__name__)

def _sanitize_query(q: str) -> str:
    """
    Pixabay é sensível a queries muito longas / com pontuação estranha.
    Mantemos letras/números/espaços, colapsamos whitespace e truncamos.
    """
    s = (q or "").strip()
    s = re.sub(r"[^0-9A-Za-zÀ-ÿ]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    if len(s) > 100:
        s = s[:100].rsplit(" ", 1)[0].strip() or s[:100].strip()
    return s or "nature"


def search(query: str, cfg: SearchConfig) -> List[Dict[str, Any]]:
    key = (os.getenv("PIXABAY_API_KEY") or "").strip()
    proxy_base = (os.getenv("LAB_CREDENTIALS_BASE_URL") or "").strip().rstrip("/")
    proxy_token = (os.getenv("WORKSHOP_ACCESS_TOKEN") or "").strip()
    use_proxy = bool(proxy_base and proxy_token)
    if not key and not use_proxy:
        return []

    query = _sanitize_query(query)
    out: List[Dict[str, Any]] = []

    # Images
    try:
        r = get_with_retry(
            f"{proxy_base}/v1/proxy/pixabay/api/" if use_proxy else "https://pixabay.com/api/",
            params=({"q": query, "per_page": cfg.per_source, "safesearch": "true"} if use_proxy else {"key": key, "q": query, "per_page": cfg.per_source, "safesearch": "true"}),
            headers=({"Authorization": f"Bearer {proxy_token}"} if use_proxy else None),
            timeout_s=cfg.timeout_s,
            max_attempts=int(os.getenv("PIXABAY_MAX_ATTEMPTS", "3")),
            base_backoff_s=float(os.getenv("PIXABAY_BACKOFF_S", "1.0")),
            provider="pixabay",
        )
        if r.status_code == 429:
            logger.warning("[pixabay] rate limited (images): status=429")
            return out
        if r.status_code >= 400:
            logger.warning("[pixabay] image search falhou: status=%s body≈%r", r.status_code, (r.text or "")[:240])
            return out
        data = r.json()
        if isinstance(data, dict) and data.get("error"):
            logger.warning("[pixabay] error payload (images): %s", data.get("error"))
            return out
        for it in (data.get("hits", []) or [])[: cfg.per_source]:
            out.append(
                {
                    "asset_type": "image",
                    "url": it.get("pageURL", ""),
                    "preview_url": it.get("largeImageURL", "") or it.get("webformatURL", ""),
                    "source": "pixabay",
                    "license": "Pixabay License (free to use)",
                    "author": it.get("user", ""),
                    "tags": it.get("tags", "") or "",
                    "width": it.get("imageWidth"),
                    "height": it.get("imageHeight"),
                }
            )
    except Exception as e:
        logger.warning("[pixabay] images: %s", e)

    # Videos
    try:
        r = get_with_retry(
            f"{proxy_base}/v1/proxy/pixabay/api/videos/" if use_proxy else "https://pixabay.com/api/videos/",
            params=({"q": query, "per_page": cfg.per_source, "safesearch": "true"} if use_proxy else {"key": key, "q": query, "per_page": cfg.per_source, "safesearch": "true"}),
            headers=({"Authorization": f"Bearer {proxy_token}"} if use_proxy else None),
            timeout_s=cfg.timeout_s,
            max_attempts=int(os.getenv("PIXABAY_MAX_ATTEMPTS", "3")),
            base_backoff_s=float(os.getenv("PIXABAY_BACKOFF_S", "1.0")),
            provider="pixabay",
        )
        if r.status_code == 429:
            logger.warning("[pixabay] rate limited (videos): status=429")
            return out
        if r.status_code >= 400:
            logger.warning("[pixabay] video search falhou: status=%s body≈%r", r.status_code, (r.text or "")[:240])
            return out
        data = r.json()
        if isinstance(data, dict) and data.get("error"):
            logger.warning("[pixabay] error payload (videos): %s", data.get("error"))
            return out
        for it in (data.get("hits", []) or [])[: cfg.per_source]:
            videos = it.get("videos", {}) or {}
            link = ""
            vw = None
            vh = None
            for k in ("large", "medium", "small", "tiny"):
                if isinstance(videos.get(k), dict) and videos[k].get("url"):
                    link = videos[k]["url"]
                    vw = videos[k].get("width", vw)
                    vh = videos[k].get("height", vh)
                    break
            out.append(
                {
                    "asset_type": "video",
                    "url": link or it.get("pageURL", ""),
                    "preview_url": str(it.get("picture_id", "")).strip(),
                    "source": "pixabay",
                    "license": "Pixabay License (free to use)",
                    "author": it.get("user", ""),
                    "tags": it.get("tags", "") or "",
                    "width": vw,
                    "height": vh,
                }
            )
    except Exception as e:
        logger.warning("[pixabay] videos: %s", e)

    return out

