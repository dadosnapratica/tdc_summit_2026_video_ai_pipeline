"""Sinais Google Trends (pytrends) — best-effort; nunca bloqueia o pipeline."""
from __future__ import annotations

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def fetch_related_and_interest(keyword: str, *, geo: str = "BR", days: int = 7) -> Dict[str, Any]:
    keyword = (keyword or "").strip()
    if not keyword:
        return {"error": "empty_keyword"}

    try:
        from pytrends.request import TrendReq
    except ImportError as e:
        logger.warning("[trends] pytrends não disponível: %s", e)
        return {"error": "pytrends_unavailable", "detail": str(e)}

    try:
        pytrends = TrendReq(hl="pt-BR", tz=180)
        pytrends.build_payload([keyword], cat=0, timeframe=f"now {int(days)}-d", geo=geo, gprop="")
        related = pytrends.related_queries() or {}
        iot = pytrends.interest_over_time() or None
        iot_dict: Dict[str, Any] = {}
        if iot is not None and hasattr(iot, "to_dict"):
            try:
                iot_dict = {"columns": list(iot.columns), "rows": iot.reset_index().to_dict(orient="records")}
            except Exception:
                iot_dict = {"note": "interest_over_time present but not serializable"}
        return {"related_queries": related, "interest_over_time": iot_dict}
    except Exception as e:
        logger.warning("[trends] falha ao obter sinais: %s", e)
        return {"error": "pytrends_failed", "detail": str(e)}


def top_titles_from_youtube(videos: List[Dict[str, Any]], *, limit: int = 10) -> List[str]:
    out: List[str] = []
    for v in videos[:limit]:
        t = str(v.get("title", "")).strip()
        if t:
            out.append(t)
    return out


def top_views_from_youtube(videos: List[Dict[str, Any]], *, limit: int = 10) -> List[str]:
    out: List[str] = []
    for v in videos[:limit]:
        out.append(str(v.get("views", "0")))
    return out
