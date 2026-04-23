"""asset_agent — multi-fonte + curadoria LLM + download para job_path/assets."""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List

import requests

from backend.agents.asset_sources import (
    DEFAULT_STYLE_GUIDE,
    SearchConfig,
    heuristic_best,
    resolve_asset_research_preference_from_env,
    search_all_for_scene,
)
from backend.agents.prompt_loader import load_prompt
from backend.core.json_utils import parse_llm_json_safe
from backend.core.llm_gateway import llm
from backend.core.paths import make_job_path

# Re-export para `scripts/run_pipeline.py` (contrato documentado em `.cursorrules`).
__all__ = ["asset_agent", "make_job_path"]
from backend.core.state import VideoState

logger = logging.getLogger(__name__)


def _download(url: str, dest_path: str, timeout: int = 60) -> bool:
    if not url:
        return False
    try:
        r = requests.get(url, stream=True, timeout=timeout)
        r.raise_for_status()
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        with open(dest_path, "wb") as f:
            for chunk in r.iter_content(65536):
                if chunk:
                    f.write(chunk)
        return os.path.isfile(dest_path) and os.path.getsize(dest_path) > 0
    except Exception as e:
        logger.warning("[asset_agent] download falhou %s: %s", url[:80], e)
        return False


def _pick_index_llm(candidates: List[Dict[str, Any]], *, scene: str, prefer: str) -> int:
    tmpl = load_prompt("asset_agent/asset_curation")
    items = []
    for i, c in enumerate(candidates[:20]):
        items.append(
            {
                "i": i,
                "asset_type": c.get("asset_type"),
                "source": c.get("source"),
                "license": c.get("license"),
                "preview_url": (str(c.get("preview_url", "")) or "")[:300],
                "url": (str(c.get("url", "")) or "")[:300],
                "text": (str(c.get("text", "") or c.get("tags", "")))[:200],
            }
        )
    mode_hint = {
        "video_first": "Prefira vídeos quando empatar em relevância; imagem só se for claramente melhor.",
        "image_first": "Prefira imagens quando empatar; vídeo só se for claramente melhor.",
        "all": "Imagem e vídeo em pé de igualdade; escolha só por relevância à cena e licença.",
        "video": "Escolha apenas entre candidatos do tipo vídeo.",
        "image": "Escolha apenas entre candidatos do tipo imagem.",
    }.get(prefer, "")
    system = "Curador de assets visuais (imagem ou vídeo). Responda só JSON."
    prompt = (
        f"{tmpl}\n\nPreferência de mídia: {prefer}. {mode_hint}\n\nCena:\n{scene}\n\n"
        f"Candidatos:\n{json.dumps(items, ensure_ascii=False)}"
    )
    try:
        raw = llm.chat(prompt, system)
        data = parse_llm_json_safe(raw, default={})
        if isinstance(data, dict):
            pi = data.get("pick_index")
            if isinstance(pi, int) and 0 <= pi < len(candidates):
                return pi
    except Exception as e:
        logger.warning("[asset_agent] curadoria LLM falhou: %s", e)
    return heuristic_best(candidates, query=scene)


def asset_agent(state: VideoState) -> VideoState:
    job_path = (state.get("job_path") or "").strip()
    if not job_path:
        job_path = make_job_path(state.get("channel_niche") or "job")

    scenes: List[str] = list(state.get("scenes") or [])
    if not scenes:
        return {**state, "job_path": job_path, "raw_assets": []}

    cfg = SearchConfig(
        per_source=int(os.getenv("ASSET_PER_SOURCE", "4")),
        timeout_s=int(os.getenv("ASSET_HTTP_TIMEOUT", "25")),
    )
    raw_assets: List[Dict[str, Any]] = []

    style_guide = (
        (os.getenv("ASSET_DEFAULT_STYLE_GUIDE") or "").strip()
        or (os.getenv("IMAGE_RESEARCH_STYLE_GUIDE") or "").strip()
        or DEFAULT_STYLE_GUIDE
    )
    research_pref = resolve_asset_research_preference_from_env()

    for idx, scene in enumerate(scenes):
        candidates = search_all_for_scene(scene, style_guide=style_guide, cfg=cfg)
        pool = list(candidates)
        if research_pref in ("video", "image"):
            filt = [c for c in pool if str(c.get("asset_type", "")).lower() == research_pref]
            if filt:
                pool = filt
        pick = -1
        if pool:
            use_llm = os.getenv("ASSET_CURATION", "llm").strip().lower() in ("1", "true", "yes", "llm")
            pick = (
                _pick_index_llm(pool, scene=scene, prefer=research_pref)
                if use_llm
                else heuristic_best(pool, query=scene, prefer=research_pref)
            )
        chosen: Dict[str, Any] | None = None
        if pick >= 0 and pick < len(pool):
            chosen = pool[pick]
        elif pool:
            chosen = pool[0]

        local_path = ""
        url = ""
        source = ""
        license_ = ""
        asset_type = ""
        if chosen:
            asset_type = str(chosen.get("asset_type") or "")
            # Para download: preferir um link direto (preview_url quase sempre é direto em imagens).
            # Em vídeos, o provider deve preencher `url` com o mp4 direto quando possível.
            url = str(chosen.get("url") or chosen.get("preview_url") or "")
            source = str(chosen.get("source") or "")
            license_ = str(chosen.get("license") or "")
            ext = ".bin"
            ul = url.lower()
            if asset_type.lower() == "video" or ".mp4" in ul:
                ext = ".mp4"
            elif ".png" in ul:
                ext = ".png"
            elif ".jpg" in ul or ".jpeg" in ul:
                ext = ".jpg"
            else:
                ext = ".jpg" if asset_type.lower() != "video" else ".mp4"
            local_path = os.path.join(job_path, "assets", f"scene_{idx:02d}_raw{ext}")
            if not _download(url, local_path):
                local_path = ""

        raw_assets.append(
            {
                "scene_idx": idx,
                "url": url,
                "local_path": local_path,
                "source": source,
                "license": license_,
                "asset_type": asset_type,
            }
        )

    return {**state, "job_path": job_path, "raw_assets": raw_assets}
