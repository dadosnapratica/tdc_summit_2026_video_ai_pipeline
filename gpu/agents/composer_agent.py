"""composer_agent — concat de clipes + narração (ffmpeg; NVENC se disponível)."""
from __future__ import annotations

import logging
import os
import subprocess
from typing import List

from workshop.backend.core.state import VideoState

logger = logging.getLogger(__name__)


def _has_nvenc() -> bool:
    try:
        p = subprocess.run(
            ["ffmpeg", "-hide_banner", "-encoders"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        return p.returncode == 0 and "h264_nvenc" in (p.stdout or "")
    except Exception:
        return False


def composer_agent(state: VideoState) -> VideoState:
    job_path = (state.get("job_path") or "").strip()
    clips: List[str] = [c for c in (state.get("clips") or []) if c and os.path.isfile(c)]
    audio = str(state.get("audio_file") or "")
    out = os.path.join(job_path, "final.mp4")
    os.makedirs(os.path.join(job_path, "clips"), exist_ok=True)

    if not clips:
        logger.warning("[composer_agent] sem clipes válidos — não gera final.mp4")
        return {**state, "video_file": ""}

    list_path = os.path.join(job_path, "clips", "concat.txt")
    with open(list_path, "w", encoding="utf-8") as f:
        for c in clips:
            # ffmpeg concat demuxer requer paths escapados
            esc = c.replace("'", "'\\''")
            f.write(f"file '{esc}'\n")

    use_nvenc = _has_nvenc() and os.getenv("FFMPEG_FORCE_CPU", "").strip() not in ("1", "true", "yes")
    vcodec = "h264_nvenc" if use_nvenc else "libx264"
    if use_nvenc:
        vargs = ["-c:v", vcodec, "-preset", "p4", "-cq", "23"]
    else:
        vargs = ["-c:v", vcodec, "-preset", "veryfast", "-crf", "23"]

    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_path]
    if audio and os.path.isfile(audio):
        cmd += ["-i", audio, "-shortest", *vargs, "-c:a", "aac", "-b:a", "192k"]
    else:
        logger.warning("[composer_agent] narration.wav ausente — vídeo sem áudio")
        cmd += [*vargs, "-an"]

    cmd += [
        "-vf",
        "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080",
        out,
    ]

    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        logger.error("[composer_agent] ffmpeg falhou: %s", e)
        return {**state, "video_file": ""}

    return {**state, "video_file": out if os.path.isfile(out) else ""}
