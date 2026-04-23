"""Busca multi-fonte de assets (Pexels, Pixabay, Unsplash, NASA, Wikimedia).

Este módulo mantém a API existente (para compatibilidade), mas delega as integrações
HTTP para providers em `agents/asset_providers/`.
"""
from __future__ import annotations

import logging
import os
import re
from typing import Any, Dict, List, Set

from workshop.backend.agents.asset_providers import nasa as nasa_provider
from workshop.backend.agents.asset_providers import pexels as pexels_provider
from workshop.backend.agents.asset_providers import pixabay as pixabay_provider
from workshop.backend.agents.asset_providers import unsplash as unsplash_provider
from workshop.backend.agents.asset_providers import wikimedia as wikimedia_provider
from workshop.backend.agents.asset_sources_common import SearchConfig, safe_get

logger = logging.getLogger(__name__)

DEFAULT_STYLE_GUIDE = (
    "cinematic documentary, realistic, high detail, 16:9, 1080p, no text, no logos, no watermarks"
)


def _clean_scene_prompt(scene: str) -> str:
    s = (scene or "").strip()
    s = re.sub(r"^\s*scene\s*\d+\s*:\s*", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\bstyle\s*:\s*.*$", "", s, flags=re.IGNORECASE).strip()
    return s


def _make_query(scene: str, style: str) -> str:
    scene_clean = _clean_scene_prompt(scene)
    tokens = re.findall(r"[a-zA-Z0-9]+", scene_clean.lower())
    stop = {
        "with",
        "and",
        "the",
        "a",
        "an",
        "of",
        "to",
        "in",
        "on",
        "no",
        "wide",
        "shot",
        "close",
        "up",
        "style",
        "realistic",
        "cinematic",
        "documentary",
        "high",
        "detail",
        "text",
        "logos",
        "watermarks",
        "image",
        "video",
    }
    keywords = [t for t in tokens if t not in stop]
    keywords = keywords[:8] if keywords else tokens[:6]
    style_tokens = re.findall(r"[a-zA-Z0-9]+", (style or "").lower())
    style_hint: List[str] = []
    for t in style_tokens:
        # Apenas termos de estilo (evitar enviesar nichos).
        if t in ("realistic", "cinematic", "documentary", "photorealistic", "film", "filmic"):
            style_hint.append(t)
        if len(style_hint) >= 2:
            break
    q = " ".join(keywords + style_hint).strip()
    return q or scene_clean or "stock footage"


def normalize_asset_research_preference(raw: str | None) -> str:
    """
    Estratégias: video_first | image_first | all | video | image
    Legado: any → all; IMAGE_RESEARCH_PREFER ainda aceito via resolve_*.
    """
    v = (raw or "").strip().lower()
    if v == "any":
        v = "all"
    if v in ("videos_first", "video-first"):
        return "video_first"
    if v in ("images_first", "image-first"):
        return "image_first"
    if v in ("video_first", "image_first", "all", "video", "image"):
        return v
    return "video_first"


def resolve_asset_research_preference_from_env() -> str:
    return normalize_asset_research_preference(
        os.getenv("ASSET_RESEARCH_PREFERENCE") or os.getenv("IMAGE_RESEARCH_PREFER")
    )


def enabled_sources() -> Set[str]:
    raw = (os.getenv("IMAGE_RESEARCH_SOURCES") or "").strip()
    if raw:
        return {s.strip().lower() for s in raw.split(",") if s.strip()}
    return {"pexels", "pixabay", "unsplash", "nasa", "wikimedia"}


def search_all_for_scene(scene_prompt: str, *, style_guide: str = DEFAULT_STYLE_GUIDE, cfg: SearchConfig | None = None) -> List[Dict[str, Any]]:
    cfg = cfg or SearchConfig()
    query = _make_query(scene_prompt, style_guide)
    enabled = enabled_sources()
    assets: List[Dict[str, Any]] = []
    if "pexels" in enabled:
        assets.extend(pexels_provider.search(query, cfg))
    if "pixabay" in enabled:
        assets.extend(pixabay_provider.search(query, cfg))
    if "unsplash" in enabled:
        assets.extend(unsplash_provider.search(query, cfg))
    if "nasa" in enabled:
        assets.extend(nasa_provider.search(query, cfg))
    if "wikimedia" in enabled:
        assets.extend(wikimedia_provider.search(query, cfg))
    for i, a in enumerate(assets):
        a["_idx"] = i
    return assets


def heuristic_best(
    assets: List[Dict[str, Any]],
    *,
    query: str,
    prefer: str | None = None,
) -> int:
    if not assets:
        return -1
    pref = normalize_asset_research_preference(prefer or resolve_asset_research_preference_from_env())

    indices = list(range(len(assets)))
    if pref in ("video", "image"):
        filtered = [i for i in indices if str(assets[i].get("asset_type", "")).lower() == pref]
        if filtered:
            indices = filtered

    qtok = set(re.findall(r"[a-zA-Z0-9]+", (query or "").lower()))

    def score_idx(i: int) -> float:
        a = assets[i]
        text = " ".join(str(a.get(k, "")) for k in ("url", "preview_url", "text", "tags", "author"))
        atok = set(re.findall(r"[a-zA-Z0-9]+", text.lower()))
        base = float(len(qtok & atok))
        at = str(a.get("asset_type", "")).lower()
        if pref == "video_first":
            base += 0.35 if at == "video" else (-0.05 if at == "image" else 0.0)
        elif pref == "image_first":
            base += 0.25 if at == "image" else (-0.05 if at == "video" else 0.0)
        return base

    return max(indices, key=score_idx)
