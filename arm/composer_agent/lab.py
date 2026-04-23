"""Laboratório do composer_agent — espelha ``agents.composer_agent``."""

from __future__ import annotations

import glob
import logging
import os
import re
from typing import Any, Dict, List

from backend.core.state import VideoState
from gpu.agents.composer_agent import composer_agent

logger = logging.getLogger(__name__)


def _sorted_scene_clips(clips_dir: str) -> List[str]:
    pattern = os.path.join(clips_dir, "scene_*.mp4")
    files = glob.glob(pattern)

    def sort_key(p: str) -> int:
        m = re.search(r"scene_(\d+)", os.path.basename(p), re.I)
        return int(m.group(1)) if m else 0

    return sorted(files, key=sort_key)


def run_composer_lab(job_path: str) -> Dict[str, Any]:
    """Gera ``final.mp4`` a partir de ``clips/scene_*.mp4`` e opcionalmente ``narration.wav``."""
    base = (job_path or "").strip()
    if not base or not os.path.isdir(base):
        return {"ok": False, "error": "job_path inválido", "video_path": ""}

    clips_dir = os.path.join(base, "clips")
    clips = [c for c in _sorted_scene_clips(clips_dir) if os.path.isfile(c) and os.path.getsize(c) > 0]
    audio = os.path.join(base, "narration.wav")
    has_audio = os.path.isfile(audio) and os.path.getsize(audio) > 0

    state: VideoState = {
        "channel_niche": "lab",
        "job_path": base,
        "topic": "",
        "angle": "",
        "trending_data": {},
        "script": "",
        "scenes": [],
        "raw_assets": [],
        "clips": clips,
        "audio_file": audio if has_audio else "",
        "video_file": "",
        "metadata": {},
        "thumbnail": {},
        "publish_status": None,
    }
    if not clips:
        return {"ok": False, "error": "sem clipes scene_*.mp4 no job", "video_path": ""}

    try:
        out = composer_agent(state)
    except Exception as e:
        logger.exception("[composer_agent.lab] composer_agent falhou")
        return {"ok": False, "error": str(e), "video_path": ""}

    vf = str(out.get("video_file") or "").strip()
    ok = bool(vf and os.path.isfile(vf) and os.path.getsize(vf) > 0)
    return {
        "ok": ok,
        "error": "" if ok else "final.mp4 não gerado",
        "video_path": vf if ok else "",
    }
