from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple

import requests

from arm.research_agent.providers.youtube_data import get_videos_by_topic

logger = logging.getLogger(__name__)


def _normalize_related_query_rows(rows: Any) -> List[Dict[str, Any]]:
    """Converte linhas de related_queries (list[dict]) em {query, value}."""
    if not isinstance(rows, list):
        return []
    out: List[Dict[str, Any]] = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        q = r.get("query")
        if q is None or (isinstance(q, float) and str(q) == "nan"):
            keys = [k for k in r.keys() if str(k).lower() != "value" and str(k).lower() != "score"]
            if keys:
                q = r.get(keys[0])
        val = r.get("value")
        if val is None:
            for k, v in r.items():
                lk = str(k).lower()
                if lk not in ("query", "index") and v is not None and str(v) != "nan":
                    val = v
                    break
        qs = str(q or "").strip()
        if not qs:
            continue
        if isinstance(val, float) and val == val:  # not NaN
            vs: Any = int(val) if val == int(val) else round(val, 2)
        else:
            vs = val if val is not None and str(val) != "nan" else ""
        out.append({"query": qs, "value": vs})
    return out


def _dict_get_ci(d: Dict[str, Any], *candidates: str) -> Any:
    """Busca valor com chave case-insensitive (JSON / serialização variam)."""
    if not isinstance(d, dict) or not d:
        return None
    lower_map = {str(k).lower(): k for k in d.keys()}
    for name in candidates:
        orig = lower_map.get(name.lower())
        if orig is not None:
            return d.get(orig)
    return None


def _extract_related_rising_top(related_queries: Any, seed_keyword: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    rising: List[Dict[str, Any]] = []
    top: List[Dict[str, Any]] = []
    if isinstance(related_queries, str):
        try:
            related_queries = json.loads(related_queries)
        except Exception:
            return rising, top
    if not isinstance(related_queries, dict) or not related_queries:
        return rising, top
    seed_lower = (seed_keyword or "").strip().lower()
    key: Optional[str] = None
    for k in related_queries.keys():
        if str(k).strip().lower() == seed_lower:
            key = str(k)
            break
    if key is None:
        keys = [str(k) for k in related_queries.keys()]
        if not keys:
            return rising, top
        key = keys[0]
    bucket = related_queries.get(key)
    if not isinstance(bucket, dict):
        return rising, top
    rising = _normalize_related_query_rows(_dict_get_ci(bucket, "rising", "Rising"))
    top = _normalize_related_query_rows(_dict_get_ci(bucket, "top", "Top"))
    # Fallback: alguns payloads aninham só um dos dois no primeiro termo disponível
    if not rising and not top:
        for b in related_queries.values():
            if not isinstance(b, dict):
                continue
            rising = _normalize_related_query_rows(_dict_get_ci(b, "rising", "Rising"))
            top = _normalize_related_query_rows(_dict_get_ci(b, "top", "Top"))
            if rising or top:
                break
    return rising, top


def _clean_json_from_llm(raw: str) -> str:
    s = (raw or "").strip()
    if s.startswith("```"):
        s = s.removeprefix("```json").removeprefix("```").strip()
        if s.endswith("```"):
            s = s.removesuffix("```").strip()
    return s


def _ollama_chat_json(prompt: str, *, system: str = "") -> Dict[str, Any]:
    base_url = (os.getenv("OLLAMA_BASE_URL") or "http://gpu-server-01:11434").rstrip("/")
    model = os.getenv("OLLAMA_MODEL") or "llama3"
    url = f"{base_url}/api/chat"
    tok = (os.getenv("WORKSHOP_ACCESS_TOKEN") or "").strip().strip('"')
    headers = {"Authorization": f"Bearer {tok}"} if tok and "/v1/proxy/" in base_url else {}
    messages: List[Dict[str, str]] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    payload = {"model": model, "messages": messages, "stream": False, "options": {"temperature": 0.25}}

    last_err: Exception | None = None
    for attempt in range(1, 4):
        try:
            r = requests.post(url, json=payload, timeout=120, headers=headers)
            r.raise_for_status()
            data = r.json()
            msg = data.get("message", {}) if isinstance(data, dict) else {}
            content = str(msg.get("content", "")).strip()
            clean = _clean_json_from_llm(content)
            return json.loads(clean)
        except Exception as e:
            last_err = e
            time.sleep(0.6 * attempt)

    raise RuntimeError(f"Falha ao chamar Ollama em {url} (model={model}): {last_err}")


def _heuristic_rank_suggestions(suggestions: List[Dict[str, Any]], *, keyword: str) -> List[Dict[str, Any]]:
    kw = set(re.findall(r"[a-zA-Z0-9]+", (keyword or "").lower()))
    scored: List[Tuple[float, Dict[str, Any]]] = []
    for s in suggestions:
        text = " ".join(
            [
                str(s.get("title", "")),
                str(s.get("subtitle", "")),
                str(s.get("kind", "")),
                str(s.get("source", "")),
            ]
        ).lower()
        tokens = set(re.findall(r"[a-zA-Z0-9]+", text))
        overlap = len(tokens & kw)
        views = 0
        try:
            views = int(str(s.get("views", "0")).replace(",", ""))
        except Exception:
            views = 0
        score = overlap * 3.0 + (views / 1_000_000.0) * 0.25
        scored.append((score, s))

    scored.sort(key=lambda x: x[0], reverse=True)
    out: List[Dict[str, Any]] = []
    for rank, (score, s) in enumerate(scored, start=1):
        item = dict(s)
        item["rank"] = rank
        item["score"] = float(score)
        out.append(item)
    return out


def _llm_rank_suggestions(suggestions: List[Dict[str, Any]], *, keyword: str) -> List[Dict[str, Any]]:
    system = (
        "Você é um editor-chefe de canal de YouTube. Rankeie sugestões de tema/ângulo para um vídeo. "
        "Retorne APENAS JSON."
    )
    items = []
    for i, s in enumerate(suggestions[:40]):
        items.append(
            {
                "id": i,
                "title": s.get("title", ""),
                "subtitle": s.get("subtitle", ""),
                "kind": s.get("kind", ""),
                "source": s.get("source", ""),
                "views": s.get("views", ""),
            }
        )
    prompt = (
        f"Keyword/tema alvo: {keyword}\n\n"
        "Sugestões:\n"
        f"{json.dumps(items, ensure_ascii=False)}\n\n"
        "Retorne APENAS este JSON:\n"
        '{"order":[<ids em ordem decrescente de relevância>], "reason":"<curto>"}'
    )
    resp = _ollama_chat_json(prompt, system=system)
    order = resp.get("order", [])
    reason = str(resp.get("reason", "")).strip()

    if not isinstance(order, list) or not order:
        raise ValueError("order inválido")

    ranked: List[Dict[str, Any]] = []
    used = set()
    rank = 1
    for oid in order:
        if not isinstance(oid, int) or oid < 0 or oid >= len(suggestions):
            continue
        if oid in used:
            continue
        used.add(oid)
        item = dict(suggestions[oid])
        item["rank"] = rank
        item["score"] = float(len(order) - rank + 1)
        item["ranker_reason"] = reason
        ranked.append(item)
        rank += 1

    # append leftovers
    for i, s in enumerate(suggestions):
        if i in used:
            continue
        item = dict(s)
        item["rank"] = rank
        item["score"] = 0.0
        item["ranker_reason"] = reason
        ranked.append(item)
        rank += 1

    return ranked


def build_research_pack(
    keyword: str,
    *,
    region: str = "BR",
    category_id: str = "28",
    youtube_n: int = 10,
    trends_days: int = 7,
) -> Dict[str, Any]:
    """
    Unifica sinais de trends (pytrends) + vídeos populares por busca (YouTube Data API)
    e gera uma lista de sugestões clicáveis para alimentar o script_agent (lab).
    """
    keyword = (keyword or "").strip()
    if not keyword:
        raise ValueError("keyword vazio")

    trends: Dict[str, Any] = {}
    try:
        from arm.research_agent.providers.pytrends_experiment import (
            TrendsConfig,
            fetch_google_trends_signals,
        )

        trends_cfg = TrendsConfig(geo=region, days=int(trends_days))
        trends = fetch_google_trends_signals([keyword], trends_cfg)
    except ImportError as e:
        logger.warning("[pytrends] indisponível (ImportError): %s", e)
        trends = {"error": "pytrends_unavailable", "detail": str(e)}
    except Exception as e:
        logger.warning("[pytrends] falhou: %s", e)
        trends = {"error": "pytrends_failed", "detail": str(e)}

    videos = []
    try:
        videos = get_videos_by_topic(
            keyword,
            category_id=category_id,
            region=region,
            n=int(youtube_n),
            relevance_language=os.getenv("RELEVANCE_LANGUAGE", "pt"),
            strict_language=os.getenv("STRICT_LANGUAGE", "0").strip() in ("1", "true", "True", "yes", "YES"),
        )
    except Exception as e:
        logger.warning("[youtube] busca falhou: %s", e)
        videos = []

    youtube_suggestions: List[Dict[str, Any]] = []
    for v in videos:
        desc = (v.get("description") or "").strip()
        vid = (v.get("video_id") or "").strip()
        youtube_suggestions.append(
            {
                "kind": "youtube_video",
                "source": "youtube",
                "title": v.get("title", ""),
                "subtitle": v.get("channel", ""),
                "views": v.get("views", ""),
                "video_id": vid,
                "video_url": v.get("video_url", ""),
                "description": desc,
                "payload": {
                    "tema": keyword,
                    "angulo": f"Inspirado no vídeo popular: {v.get('title','')}",
                    "youtube_context": {
                        "video_id": vid,
                        "video_url": v.get("video_url", ""),
                        "channel_url": v.get("channel_url", ""),
                        "views": v.get("views", ""),
                        "title": v.get("title", ""),
                        "description": desc,
                    },
                },
            }
        )

    ranker = (os.getenv("RESEARCH_RANKER") or "heuristic").strip().lower()
    try:
        if ranker == "ollama":
            ranked_videos = _llm_rank_suggestions(youtube_suggestions, keyword=keyword)
        else:
            ranked_videos = _heuristic_rank_suggestions(youtube_suggestions, keyword=keyword)
    except Exception as e:
        logger.warning("[research] ranker falhou (%s), fallback heuristic: %s", ranker, e)
        ranked_videos = _heuristic_rank_suggestions(youtube_suggestions, keyword=keyword)
        ranker = "heuristic_fallback"

    rel_rq = trends.get("related_queries") or {}
    rel_rising, rel_top = _extract_related_rising_top(rel_rq, keyword)
    trends_panel: Dict[str, Any] = {
        "seed_keyword": keyword,
        "geo": trends.get("geo") or region,
        "timeframe": trends.get("timeframe", ""),
        "trending_searches": list(trends.get("google_trending_searches") or [])[:50],
        "related_rising": rel_rising,
        "related_top": rel_top,
        "interest_over_time": trends.get("interest_over_time"),
    }
    if trends.get("error"):
        trends_panel["error"] = trends.get("error")
        trends_panel["error_detail"] = trends.get("detail")

    return {
        "keyword": keyword,
        "region": region,
        "category_id": category_id,
        "trends": trends,
        "youtube_videos": videos,
        "video_suggestions": ranked_videos,
        "trends_panel": trends_panel,
        "suggestions": ranked_videos,
        "ranker": ranker,
    }
