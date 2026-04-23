"""visual_agent — ComfyUI (quando workflow real existe) ou fallback ffmpeg a partir do still."""
from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from backend.runtime_paths import monorepo_root
from backend.core.state import VideoState
from gpu.agents.comfy_client import (
    collect_output_files,
    submit_prompt,
    upload_image_to_input,
    wait_for_history,
)

logger = logging.getLogger(__name__)


def is_comfy_ui_runnable(*, workflow_placeholder: bool) -> bool:
    """
    True quando ComfyUI pode correr para stills: URL definida, workflow não placeholder,
    e entrada definida por cópia local ``COMFYUI_INPUT_DIR`` ou por ``COMFYUI_INPUT_METHOD=upload``.
    """
    comfy_base = (os.getenv("COMFYUI_BASE_URL") or "").strip()
    input_dir = (os.getenv("COMFYUI_INPUT_DIR") or "").strip()
    method = (os.getenv("COMFYUI_INPUT_METHOD") or "copy").strip().lower()
    if method not in ("copy", "upload"):
        method = "copy"
    if workflow_placeholder or not comfy_base:
        return False
    if method == "upload":
        return True
    return bool(input_dir)


def env_default_visual_comfy_on() -> bool:
    """Default do laboratório: tentar ComfyUI quando ``visual_use_comfy`` não é passado explicitamente."""
    v = (os.getenv("VISUAL_USE_COMFYUI_DEFAULT") or "1").strip().lower()
    return v not in ("0", "false", "no", "off")


def resolve_use_comfy_ui(*, workflow_placeholder: bool, visual_use_comfy: Optional[bool]) -> bool:
    """
    ``visual_use_comfy``:
    - False → nunca ComfyUI
    - True → ComfyUI se ``is_comfy_ui_runnable``
    - None → respeita ``VISUAL_USE_COMFYUI_DEFAULT`` + ``is_comfy_ui_runnable``
    """
    if visual_use_comfy is False:
        return False
    gate = is_comfy_ui_runnable(workflow_placeholder=workflow_placeholder)
    if visual_use_comfy is True:
        return gate
    return env_default_visual_comfy_on() and gate


def explain_comfy_skip_reason(*, workflow_placeholder: bool, forced_no_comfy: bool = False) -> str:
    """
    Texto para UI/logs quando ComfyUI não corre.
    String vazia quando ``resolve_use_comfy_ui`` seria True (ainda assim, vídeos .mp4 são só ffmpeg).
    """
    if forced_no_comfy:
        return "Opção «sem ComfyUI» ativa — apenas ffmpeg para imagens."
    comfy_base = (os.getenv("COMFYUI_BASE_URL") or "").strip()
    input_dir = (os.getenv("COMFYUI_INPUT_DIR") or "").strip()
    method = (os.getenv("COMFYUI_INPUT_METHOD") or "copy").strip().lower()
    if method not in ("copy", "upload"):
        method = "copy"
    if workflow_placeholder:
        return (
            "O ficheiro config/comfyui_animatediff_workflow.json ainda tem "
            '"__PLACEHOLDER__": true — exporte o workflow AnimateDiff/img2img a partir do ComfyUI '
            "e substitua o JSON; defina então \"__PLACEHOLDER__\": false."
        )
    if not comfy_base:
        return "COMFYUI_BASE_URL não está definido."
    if method == "copy" and not input_dir:
        return (
            "COMFYUI_INPUT_METHOD=copy exige COMFYUI_INPUT_DIR (pasta de input do ComfyUI), "
            "ou defina COMFYUI_INPUT_METHOD=upload para enviar imagens por API."
        )
    return ""

_REPO_ROOT = monorepo_root()


def _load_workflow(rel: str) -> Dict[str, Any]:
    p = _REPO_ROOT / "config" / rel
    if not p.is_file():
        return {"__PLACEHOLDER__": True}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning("[visual_agent] workflow inválido %s: %s", p, e)
        return {"__PLACEHOLDER__": True}


def _deep_replace(obj: Any, mapping: Dict[str, str]) -> Any:
    if isinstance(obj, str):
        s = obj
        for k, v in mapping.items():
            s = s.replace(k, v)
        return s
    if isinstance(obj, list):
        return [_deep_replace(x, mapping) for x in obj]
    if isinstance(obj, dict):
        return {str(k): _deep_replace(v, mapping) for k, v in obj.items()}
    return obj


def _ffmpeg_still_to_clip(image_path: str, out_mp4: str, *, seconds: float = 2.0) -> bool:
    os.makedirs(os.path.dirname(out_mp4), exist_ok=True)
    # Para imagem estática, usar -loop 1 (mais compatível/estável que -stream_loop -1).
    # pad com x/y: centra no 16:9.
    vf = (
        "scale=1920:1080:force_original_aspect_ratio=decrease,"
        "pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=black,"
        "format=yuv420p"
    )
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-y",
        "-loop",
        "1",
        "-i",
        image_path,
        "-t",
        str(seconds),
        "-r",
        "30",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-an",
        "-vf",
        vf,
        out_mp4,
    ]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if p.returncode != 0:
            err = (p.stderr or p.stdout or "").strip()
            logger.warning(
                "[visual_agent] ffmpeg fallback exit=%s: %s",
                p.returncode,
                err[-2000:] if err else "(sem stderr)",
            )
            return False
        return os.path.isfile(out_mp4) and os.path.getsize(out_mp4) > 0
    except Exception as e:
        logger.warning("[visual_agent] ffmpeg fallback falhou: %s", e)
        return False


def _ffmpeg_video_to_clip(video_path: str, out_mp4: str, *, seconds: float = 2.0) -> bool:
    os.makedirs(os.path.dirname(out_mp4), exist_ok=True)
    vf = (
        "scale=1920:1080:force_original_aspect_ratio=decrease,"
        "pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=black,"
        "format=yuv420p"
    )
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-y",
        "-i",
        video_path,
        "-t",
        str(seconds),
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-an",
        "-vf",
        vf,
        out_mp4,
    ]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
        if p.returncode != 0:
            err = (p.stderr or p.stdout or "").strip()
            logger.warning(
                "[visual_agent] ffmpeg video->clip exit=%s: %s",
                p.returncode,
                err[-2000:] if err else "(sem stderr)",
            )
            return False
        return os.path.isfile(out_mp4) and os.path.getsize(out_mp4) > 0
    except Exception as e:
        logger.warning("[visual_agent] ffmpeg video->clip falhou: %s", e)
        return False


def _download_view(base_url: str, filename: str, subfolder: str, dest: str) -> bool:
    base_url = base_url.rstrip("/")
    params = {"filename": filename, "subfolder": subfolder, "type": "output"}
    try:
        r = requests.get(f"{base_url}/view", params=params, timeout=120, stream=True)
        r.raise_for_status()
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "wb") as f:
            for chunk in r.iter_content(65536):
                if chunk:
                    f.write(chunk)
        return os.path.isfile(dest) and os.path.getsize(dest) > 0
    except Exception as e:
        logger.warning("[visual_agent] download view falhou: %s", e)
        return False


def visual_agent(state: VideoState, *, visual_use_comfy: Optional[bool] = None) -> VideoState:
    job_path = (state.get("job_path") or "").strip()
    raw_assets: List[Dict[str, Any]] = list(state.get("raw_assets") or [])
    comfy_base = (os.getenv("COMFYUI_BASE_URL") or "").strip().rstrip("/")
    input_dir = (os.getenv("COMFYUI_INPUT_DIR") or "").strip()
    input_method = (os.getenv("COMFYUI_INPUT_METHOD") or "copy").strip().lower()
    if input_method not in ("copy", "upload"):
        input_method = "copy"

    wf_ad = _load_workflow("comfyui_animatediff_workflow.json")
    wf_placeholder = bool(wf_ad.get("__PLACEHOLDER__"))
    use_comfy = resolve_use_comfy_ui(workflow_placeholder=wf_placeholder, visual_use_comfy=visual_use_comfy)

    clips_dir = os.path.join(job_path, "clips")
    os.makedirs(clips_dir, exist_ok=True)
    clips: List[str] = []

    mapping = {
        "__CKPT_NAME__": (os.getenv("COMFYUI_MODEL") or "").strip(),
        "__AD_MODEL__": (os.getenv("ANIMATEDIFF_MODEL") or "").strip(),
        "__IMG2IMG_STRENGTH__": str(os.getenv("IMG2IMG_STRENGTH", "0.45")),
    }

    for asset in sorted(raw_assets, key=lambda a: int(a.get("scene_idx", 0) or 0)):
        idx = int(asset.get("scene_idx", 0) or 0)
        lp = str(asset.get("local_path") or "")
        out_clip = os.path.join(clips_dir, f"scene_{idx:02d}.mp4")
        ok = False
        seconds = float(os.getenv("VISUAL_FALLBACK_CLIP_SECONDS", "2.0"))

        # Se o asset já é vídeo, o nosso trabalho aqui é normalizar para um mp4 curto por cena
        # (o composer concatena apenas vídeos).
        if lp and os.path.isfile(lp) and lp.lower().endswith(".mp4"):
            ok = _ffmpeg_video_to_clip(lp, out_clip, seconds=seconds)
            clips.append(out_clip if ok else "")
            continue

        if lp and os.path.isfile(lp) and use_comfy and (input_method == "upload" or input_dir):
            try:
                if input_method == "upload":
                    basename_wf, _upload_sub = upload_image_to_input(comfy_base, lp)
                else:
                    basename_wf = os.path.basename(lp)
                    dest_in = os.path.join(input_dir, basename_wf)
                    shutil.copy2(lp, dest_in)
                wf = _deep_replace(wf_ad, {**mapping, "__INPUT_BASENAME__": basename_wf})
                if isinstance(wf, dict) and "__README" in wf:
                    del wf["__README"]
                if isinstance(wf, dict) and "__PLACEHOLDER__" in wf:
                    del wf["__PLACEHOLDER__"]
                pid = submit_prompt(comfy_base, wf)
                hist = wait_for_history(comfy_base, pid, timeout_s=float(os.getenv("COMFYUI_TIMEOUT_S", "900")))
                files = collect_output_files(hist)
                # Prefer mp4
                mp4s = [f for f in files if f[0].lower().endswith(".mp4")]
                pick = mp4s[0] if mp4s else files[0] if files else None
                if pick:
                    ok = _download_view(comfy_base, pick[0], pick[1], out_clip)
            except Exception as e:
                logger.warning("[visual_agent] ComfyUI falhou cena %s: %s", idx, e)

        if not ok and lp and os.path.isfile(lp):
            ok = _ffmpeg_still_to_clip(lp, out_clip, seconds=seconds)

        clips.append(out_clip if ok else "")

    # Remover entradas vazias no fim para manter alinhamento opcional — manter strings vazias marca falha
    return {**state, "clips": clips}
