"""metadata_agent — título, descrição, tags via LLM (formato Growth Engine opcional)."""
from __future__ import annotations

import logging
from typing import Any, Dict

from workshop.backend.agents.prompt_loader import load_prompt
from workshop.backend.core.json_utils import parse_llm_json_safe
from workshop.backend.core.llm_gateway import llm
from workshop.backend.core.state import VideoState

logger = logging.getLogger(__name__)


def metadata_agent(state: VideoState) -> VideoState:
    script = (state.get("script") or "").strip()
    topic = (state.get("topic") or "").strip()
    angle = (state.get("angle") or "").strip()
    td = state.get("trending_data") or {}

    tmpl = load_prompt("metadata_agent/metadata")
    system = tmpl + "\n\nResponda só JSON UTF-8 válido, sem markdown ou cercas ```."
    prompt = (
        f"Tema: {topic}\nÂngulo narrativo: {angle}\n\n"
        f"Roteiro (trecho):\n{script[:12000]}\n\n"
        f"Sinais de trending/research (resumo): {str(td)[:4000]}\n"
    )

    meta: Dict[str, Any] = _default_meta(topic=topic, script=script)
    try:
        raw = llm.chat(prompt, system)
        data = parse_llm_json_safe(raw, default={})
        if isinstance(data, dict):
            merged = _merge_llm_payload(data, topic=topic, angle=angle, script=script)
            meta.update(merged)
    except Exception as e:
        logger.warning("[metadata_agent] LLM fallback: %s", e)

    if isinstance(meta.get("tags"), list):
        meta["tags"] = meta["tags"][:30]

    # Campos apenas para laboratório / UI (publisher usa title, description, tags)
    meta.setdefault("title_variants", [])
    meta.setdefault("description_options", [])
    if not isinstance(meta.get("title_variants"), list):
        meta["title_variants"] = []
    if not isinstance(meta.get("description_options"), list):
        meta["description_options"] = []

    return {**state, "metadata": meta}


def _default_meta(*, topic: str, script: str) -> Dict[str, Any]:
    return {
        "title": topic or "Vídeo gerado pelo pipeline",
        "description": (script[:5000] if script else "Descrição automática."),
        "tags": [topic.lower(), "ciência", "documentário"] if topic else ["video"],
        "title_variants": [],
        "description_options": [],
    }


def _merge_llm_payload(data: Dict[str, Any], *, topic: str, angle: str, script: str) -> Dict[str, Any]:
    """Interpreta JSON rico (Growth-like) ou legado simples."""
    variants = data.get("title_variants")
    blocks = data.get("description_blocks")
    if isinstance(variants, list) or isinstance(blocks, dict):
        try:
            return _merge_rich_payload(data, topic=topic, angle=angle, script=script)
        except Exception as e:
            logger.warning("[metadata_agent] formato rico falhou (%s) — usando JSON simples.", e)

    return _merge_simple_payload(data, topic=topic, script=script)


def _merge_rich_payload(
    data: Dict[str, Any],
    *,
    topic: str,
    angle: str,
    script: str,
) -> Dict[str, Any]:
    from workshop.publish_experiments.growth_prep_lab import (
        assemble_description,
        build_chapter_lines,
        fallback_resumo,
        first_relevant_sentence,
        pick_best_title,
    )

    blocks = data.get("description_blocks")
    if not isinstance(blocks, dict):
        blocks = {}
    if not str(blocks.get("hook") or "").strip():
        blocks["hook"] = first_relevant_sentence(script, tema=topic or angle)
    if not str(blocks.get("resumo") or "").strip():
        blocks["resumo"] = fallback_resumo(script)

    chapter_titles_in: list[str] = []
    ct = data.get("chapter_titles")
    if isinstance(ct, list):
        chapter_titles_in = [str(x).strip() for x in ct if str(x).strip()]

    chapter_body, _ = build_chapter_lines([], chapter_titles_in)
    description = assemble_description(blocks, chapter_body)

    variants = data.get("title_variants")
    if not isinstance(variants, list):
        variants = []
    variants_s = [str(x).strip() for x in variants if str(x).strip()]
    llm_sel = str(data.get("selected_title") or "").strip()
    title = pick_best_title(variants_s, tema=topic or angle, prefer=llm_sel)

    tags = data.get("tags")
    if not isinstance(tags, list):
        tags = []
    tags = [str(t).strip() for t in tags if str(t).strip()][:30]

    if len(description.strip()) < 80:
        extra = script[:600].rsplit(" ", 1)[0] + "…" if len(script) > 600 else script
        description = (description + "\n\n" + extra).strip()[:5000]

    desc_opts: list[str] = []
    if description.strip():
        desc_opts.append(description.strip()[:5000])

    alts = data.get("description_alternatives")
    if isinstance(alts, list):
        for a in alts:
            s = str(a).strip()
            if s and s not in desc_opts:
                desc_opts.append(s[:5000])

    if len(desc_opts) == 0:
        desc_opts = [description[:5000]]

    return {
        "title": title[:100],
        "description": desc_opts[0][:5000],
        "tags": tags,
        "title_variants": variants_s[:15],
        "description_options": desc_opts[:5],
    }


def _merge_simple_payload(data: Dict[str, Any], *, topic: str, script: str) -> Dict[str, Any]:
    base = _default_meta(topic=topic, script=script)
    t = str(data.get("title") or "").strip()
    d = str(data.get("description") or "").strip()
    tags = data.get("tags")
    if t:
        base["title"] = t[:100]
    if d:
        base["description"] = d[:5000]
    if isinstance(tags, list):
        base["tags"] = [str(x).strip() for x in tags if str(x).strip()][:30]
    tv = data.get("title_variants")
    if isinstance(tv, list):
        base["title_variants"] = [str(x).strip() for x in tv if str(x).strip()][:15]
    elif base["title"]:
        base["title_variants"] = [base["title"]]
    do = data.get("description_options") or data.get("description_variants")
    if isinstance(do, list):
        base["description_options"] = [str(x).strip() for x in do if str(x).strip()][:5]
    elif base["description"]:
        base["description_options"] = [base["description"]]
    return base
