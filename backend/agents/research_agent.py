"""research_agent — YouTube + Trends (best-effort) + LLM para topic/angle/trending_data."""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List

from workshop.backend.agents.trends_signals import fetch_related_and_interest, top_titles_from_youtube, top_views_from_youtube
from workshop.backend.agents.youtube_client import get_videos_by_topic
from workshop.backend.core.json_utils import parse_llm_json_safe
from workshop.backend.core.llm_gateway import llm
from workshop.backend.core.state import VideoState

logger = logging.getLogger(__name__)


def _rank_videos_simple(videos: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    def _views(v: Dict[str, Any]) -> int:
        try:
            return int(str(v.get("views", "0")).replace(",", ""))
        except Exception:
            return 0

    return sorted(videos, key=_views, reverse=True)


def research_agent(state: VideoState) -> VideoState:
    niche = (state.get("channel_niche") or "").strip()
    region = (os.getenv("YOUTUBE_REGION_CODE") or "BR").strip()
    category_id = (os.getenv("YOUTUBE_CATEGORY_ID") or "28").strip()
    max_n = int(os.getenv("YOUTUBE_MAX_TRENDING_RESULTS", "10"))

    videos: List[Dict[str, Any]] = []
    try:
        videos = get_videos_by_topic(
            niche,
            category_id=category_id,
            region=region,
            n=max(10, max_n),
            relevance_language=os.getenv("RELEVANCE_LANGUAGE", "pt"),
            strict_language=os.getenv("STRICT_LANGUAGE", "0").strip() in ("1", "true", "True", "yes", "YES"),
        )
    except Exception as e:
        logger.warning("[research_agent] YouTube falhou: %s", e)
        videos = []

    videos = _rank_videos_simple(videos)[:max_n]

    trends: Dict[str, Any] = {}
    try:
        trends = fetch_related_and_interest(niche, geo=region, days=int(os.getenv("TRENDS_DAYS", "7")))
    except Exception as e:
        logger.warning("[research_agent] Trends falhou: %s", e)
        trends = {"error": str(e)}

    system = (
        "Você é pesquisador de conteúdo para YouTube em PT-BR. "
        "Com base no nicho e nos dados, escolha um tema e um ângulo narrativo claros. "
        "Responda APENAS com JSON válido no formato: "
        '{"topic": str, "angle": str, "rationale": str}'
    )
    prompt = (
        f"Nicho do canal: {niche}\n\n"
        f"Vídeos (amostra): {json.dumps(videos[:8], ensure_ascii=False)}\n\n"
        f"Sinais Trends (podem estar vazios ou com erro): {json.dumps(trends, ensure_ascii=False)[:8000]}\n"
    )
    topic = niche
    angle = f"Explorando {niche} com foco em curiosidades e ciência acessível"
    try:
        raw = llm.chat(prompt, system)
        data = parse_llm_json_safe(raw, default={})
        if isinstance(data, dict):
            topic = str(data.get("topic") or topic).strip() or topic
            angle = str(data.get("angle") or angle).strip() or angle
    except Exception as e:
        logger.warning("[research_agent] LLM fallback: %s", e)

    trending_data: Dict[str, Any] = {
        "top_titles": top_titles_from_youtube(videos, limit=max_n),
        "top_views": top_views_from_youtube(videos, limit=max_n),
        "trend_score": float(len(videos)),
        "youtube_sample": videos[:5],
        "trends": trends,
    }

    return {
        **state,
        "topic": topic,
        "angle": angle,
        "trending_data": trending_data,
    }
