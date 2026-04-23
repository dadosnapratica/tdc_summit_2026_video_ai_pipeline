"""Laboratório do tts_agent — espelha ``agents.tts_agent``."""

from __future__ import annotations

import logging
import os
from typing import Any, Dict

from backend.agents.tts_agent import tts_agent
from backend.core.state import VideoState

logger = logging.getLogger(__name__)


def run_tts_lab(script: str, job_path: str) -> Dict[str, Any]:
    """Gera ``narration.wav`` dentro de ``job_path``."""
    text = (script or "").strip()
    if not text:
        return {"ok": False, "error": "script vazio", "audio_path": ""}

    os.makedirs(job_path, exist_ok=True)
    state: VideoState = {
        "channel_niche": "lab",
        "job_path": job_path,
        "topic": "",
        "angle": "",
        "trending_data": {},
        "script": text,
        "scenes": [],
        "raw_assets": [],
        "clips": [],
        "audio_file": "",
        "video_file": "",
        "metadata": {},
        "thumbnail": {},
        "publish_status": None,
    }
    try:
        out = tts_agent(state)
    except Exception as e:
        logger.exception("[tts_agent.lab] tts_agent falhou")
        return {"ok": False, "error": str(e), "audio_path": ""}

    ap = str(out.get("audio_file") or "").strip()
    ok = bool(ap and os.path.isfile(ap) and os.path.getsize(ap) > 0)
    if ok:
        try:
            sp = os.path.join(job_path, "script_lab.txt")
            with open(sp, "w", encoding="utf-8") as f:
                f.write(text)
        except OSError as e:
            logger.warning("[tts_agent.lab] não foi possível gravar script_lab.txt: %s", e)
    return {
        "ok": ok,
        "error": "" if ok else "ficheiro de áudio inválido ou vazio",
        "audio_path": ap if ok else "",
    }
