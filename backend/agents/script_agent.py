"""script_agent — roteiro PT-BR + cenas EN via LLM."""
from __future__ import annotations

import logging
from typing import Any, List

from backend.agents.prompt_loader import load_prompt
from backend.core.json_utils import parse_llm_json_safe
from backend.core.llm_gateway import llm
from backend.core.state import VideoState

logger = logging.getLogger(__name__)


def _template_scenes(topic: str, angle: str) -> List[str]:
    base = (
        "cinematic documentary, realistic, high detail, 16:9, 1080p, "
        "no text, no logos, no watermarks"
    )
    return [
        f"Scene 1: wide establishing shot about {topic}, {angle}, {base}",
        f"Scene 2: scientific visualization concept related to {topic}, {base}",
        f"Scene 3: technology and discovery mood, {base}",
        f"Scene 4: human scale context, documentary lighting, {base}",
        f"Scene 5: dramatic highlight, space or lab aesthetic, {base}",
        f"Scene 6: calm closing wide shot, inspirational tone, {base}",
    ]


def script_agent(state: VideoState) -> VideoState:
    topic = (state.get("topic") or state.get("channel_niche") or "").strip()
    angle = (state.get("angle") or "").strip()
    niche = (state.get("channel_niche") or "").strip()
    td = state.get("trending_data") or {}

    tmpl = load_prompt("script_agent/script")
    system = "Você é roteirista de vídeo educativo em PT-BR. Siga o formato pedido."
    prompt = (
        f"{tmpl}\n\n"
        f"Tema (topic): {topic}\n"
        f"Ângulo: {angle}\n"
        f"Nicho do canal: {niche}\n"
        f"Contexto trending (resumo): {str(td)[:6000]}\n"
    )
    script = (
        f"Hoje falamos sobre {topic}. {angle} "
        "Vamos percorrer os pontos principais com clareza e bons exemplos."
    )
    scenes = _template_scenes(topic or niche, angle or "visão geral")

    try:
        raw = llm.chat(prompt, system)
        data = parse_llm_json_safe(raw, default={})
        if isinstance(data, dict):
            s = str(data.get("script") or "").strip()
            sc = data.get("scenes")
            if s:
                script = s
            if isinstance(sc, list) and sc:
                scenes = [str(x).strip() for x in sc if str(x).strip()]
    except Exception as e:
        logger.warning("[script_agent] LLM fallback: %s", e)

    return {**state, "script": script, "scenes": scenes}
