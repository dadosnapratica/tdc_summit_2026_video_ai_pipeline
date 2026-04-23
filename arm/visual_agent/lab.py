"""
Laboratório do visual_agent — espelha ``agents.visual_agent`` sem LangGraph.

Aceita uma imagem (URL http(s) ou caminho local) e gera um clipe por cena usando
o mesmo fluxo de produção (ComfyUI + AnimateDiff quando configurado, senão ffmpeg).

**Nota de deploy:** para ComfyUI remoto pode usar-se ``COMFYUI_INPUT_METHOD=upload``
(``POST /upload/image`` para o servidor ComfyUI) sem NFS; ou ``COMFYUI_INPUT_DIR`` quando
o BFF escreve no mesmo filesystem que o ComfyUI (ex. NFS montado no host do BFF).
"""

from __future__ import annotations

import logging
import os
import shutil
import tempfile
import wave
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import requests

from workshop.backend.core.state import VideoState
from workshop.gpu.agents.visual_agent import (
    explain_comfy_skip_reason,
    resolve_use_comfy_ui,
    visual_agent,
)

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _read_workflow_placeholder() -> bool:
    wf_path = _REPO_ROOT / "config" / "comfyui_animatediff_workflow.json"
    try:
        import json

        data = json.loads(wf_path.read_text(encoding="utf-8"))
        return bool(data.get("__PLACEHOLDER__", True))
    except Exception:
        return True


def _visual_lab_hints(visual_use_comfy: Optional[bool]) -> tuple[bool, str, str]:
    wf_ph = _read_workflow_placeholder()
    use_eff = resolve_use_comfy_ui(workflow_placeholder=wf_ph, visual_use_comfy=visual_use_comfy)
    mode_hint = "comfyui" if use_eff else "ffmpeg_fallback"
    forced = visual_use_comfy is False
    if forced:
        comfy_skip = explain_comfy_skip_reason(workflow_placeholder=wf_ph, forced_no_comfy=True)
    elif not use_eff:
        comfy_skip = explain_comfy_skip_reason(workflow_placeholder=wf_ph, forced_no_comfy=False)
    else:
        comfy_skip = ""
    return wf_ph, mode_hint, comfy_skip


def _guess_ext_from_url(url: str) -> str:
    path = urlparse(url).path or ""
    suf = Path(path).suffix.lower()
    if suf in (".jpg", ".jpeg", ".png", ".webp", ".gif", ".mp4", ".mov", ".m4v", ".webm"):
        return suf
    return ".bin"


def _download_media(url: str, dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    # Alguns providers retornam "page URLs" (ex.: pexels.com/photo/...) que dão 403 via scraping.
    # Nesses casos, tentamos resolver um link direto via og:image.
    u0 = (url or "").strip()
    parsed = urlparse(u0)
    if parsed.netloc.endswith("pexels.com") and "/photo/" in (parsed.path or ""):
        try:
            r0 = requests.get(
                u0,
                timeout=30,
                headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml",
                },
            )
            if r0.ok:
                html = r0.text or ""
                import re

                m = re.search(r'property=["\\\']og:image["\\\']\\s+content=["\\\']([^"\\\']+)["\\\']', html, flags=re.I)
                if m and m.group(1).strip().startswith("http"):
                    url = m.group(1).strip()
        except Exception:
            pass

    ext = _guess_ext_from_url(url)
    fd, tmp = tempfile.mkstemp(suffix=ext, prefix="lab_dl_", dir=str(dest_dir))
    os.close(fd)
    path = Path(tmp)
    try:
        r = requests.get(
            url,
            timeout=120,
            stream=True,
            headers={"User-Agent": "Mozilla/5.0", "Accept": "*/*"},
        )
        r.raise_for_status()
        ctype = (r.headers.get("Content-Type") or "").lower()
        # Ajusta extensão com base no content-type quando fizer sentido
        if "video/" in ctype and path.suffix.lower() not in (".mp4", ".webm", ".mov", ".m4v"):
            path = path.with_suffix(".mp4")
        elif "image/png" in ctype and path.suffix.lower() != ".png":
            path = path.with_suffix(".png")
        elif "image/webp" in ctype and path.suffix.lower() != ".webp":
            path = path.with_suffix(".webp")
        elif ("image/jpeg" in ctype or "image/jpg" in ctype) and path.suffix.lower() not in (".jpg", ".jpeg"):
            path = path.with_suffix(".jpg")
        with open(path, "wb") as f:
            for chunk in r.iter_content(65536):
                if chunk:
                    f.write(chunk)
        if not path.is_file() or path.stat().st_size == 0:
            raise RuntimeError("download vazio")
        return path
    except Exception:
        try:
            path.unlink(missing_ok=True)
        except Exception:
            pass
        raise


def run_visual_lab(image: str, *, scene_idx: int = 0, visual_use_comfy: Optional[bool] = None) -> Dict[str, Any]:
    """
    Executa ``visual_agent`` com um único ``raw_asset``.

    ``image`` — URL http(s) ou caminho absoluto/relativo a um ficheiro de imagem.
    """
    raw = (image or "").strip()
    if not raw:
        return {"ok": False, "error": "image vazio", "clips": [], "clip_path": "", "job_path": ""}

    job_path = tempfile.mkdtemp(prefix="ihl_visual_lab_")
    assets_dir = Path(job_path) / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    warnings: List[str] = []

    if raw.startswith("http://") or raw.startswith("https://"):
        try:
            local_path = str(_download_media(raw, assets_dir))
        except Exception as e:
            logger.warning("[visual_agent.lab] download falhou: %s", e)
            return {
                "ok": False,
                "error": f"download falhou: {e}",
                "clips": [],
                "clip_path": "",
                "job_path": job_path,
            }
    else:
        p = Path(raw).expanduser()
        if not p.is_file():
            return {
                "ok": False,
                "error": f"ficheiro não encontrado: {raw}",
                "clips": [],
                "clip_path": "",
                "job_path": job_path,
            }
        local_path = str(p.resolve())

    idx = int(scene_idx)
    dest_name = f"scene_{idx:02d}_raw{Path(local_path).suffix.lower() or '.jpg'}"
    dest = assets_dir / dest_name
    try:
        if os.path.normpath(local_path) != os.path.normpath(str(dest)):
            shutil.copy2(local_path, dest)
            local_path = str(dest)
    except Exception as e:
        return {
            "ok": False,
            "error": f"preparar asset falhou: {e}",
            "clips": [],
            "clip_path": "",
            "job_path": job_path,
        }

    workflow_placeholder, mode_hint, comfy_skip = _visual_lab_hints(visual_use_comfy)
    if comfy_skip:
        warnings.append(comfy_skip)
    if local_path.lower().endswith(".mp4"):
        warnings.append(
            "Este asset é vídeo (.mp4): o visual_agent só normaliza com ffmpeg; "
            "AnimateDiff/ComfyUI aplica-se a imagens quando o workflow está configurado."
        )

    state: VideoState = {
        "channel_niche": "lab",
        "job_path": job_path,
        "topic": "",
        "angle": "",
        "trending_data": {},
        "script": "",
        "scenes": [],
        "raw_assets": [
            {
                "scene_idx": idx,
                "local_path": local_path,
                "url": raw if raw.startswith("http") else "",
                "source": "lab",
                "license": "experimental",
            }
        ],
        "clips": [],
        "audio_file": "",
        "video_file": "",
        "metadata": {},
        "thumbnail": {},
        "publish_status": None,
    }

    try:
        out = visual_agent(state, visual_use_comfy=visual_use_comfy)
    except Exception as e:
        logger.exception("[visual_agent.lab] visual_agent falhou")
        return {
            "ok": False,
            "error": str(e),
            "clips": [],
            "clip_path": "",
            "job_path": job_path,
            "mode": mode_hint,
            "workflow_is_placeholder": workflow_placeholder,
            "comfy_skip_reason": comfy_skip,
            "warnings": warnings,
        }

    clips: List[str] = list(out.get("clips") or [])
    clip_path = ""
    for c in clips:
        if c and os.path.isfile(c) and os.path.getsize(c) > 0:
            clip_path = c
            break

    ok = bool(clip_path)
    if not ok and not warnings:
        warnings.append("nenhum clipe válido gerado (ver logs do servidor)")

    return {
        "ok": ok,
        "error": "" if ok else (warnings[-1] if warnings else "falha desconhecida"),
        "clips": clips,
        "clip_path": clip_path,
        "job_path": job_path,
        "mode": mode_hint,
        "workflow_is_placeholder": workflow_placeholder,
        "comfy_skip_reason": comfy_skip,
        "warnings": warnings,
    }


def run_visual_batch(job_path: str, items: List[Dict[str, Any]], *, visual_use_comfy: Optional[bool] = None) -> Dict[str, Any]:
    """
    Executa ``visual_agent`` com vários ``raw_assets`` (URLs ou paths locais).

    ``items`` — lista de ``{"scene_idx": int, "image": str}``.
    """
    base = (job_path or "").strip()
    if not base or not os.path.isdir(base):
        return {"ok": False, "error": "job_path inválido", "clips": [], "job_path": ""}

    rows = [x for x in (items or []) if isinstance(x, dict)]
    if not rows:
        return {"ok": False, "error": "lista de cenas vazia", "clips": [], "job_path": base}

    warnings: List[str] = []
    workflow_placeholder, mode_hint, comfy_skip = _visual_lab_hints(visual_use_comfy)
    if comfy_skip:
        warnings.append(comfy_skip)

    assets_dir = Path(base) / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    # Duração por cena (fallback ffmpeg): se houver narration.wav, distribui pela quantidade de cenas.
    wav_path = os.path.join(base, "narration.wav")
    seconds_override: float | None = None
    try:
        if os.path.isfile(wav_path) and os.path.getsize(wav_path) > 0:
            with wave.open(wav_path, "rb") as w:
                frames = w.getnframes()
                rate = w.getframerate() or 0
                dur = float(frames) / float(rate) if rate else 0.0
            n = max(1, len([x for x in (items or []) if isinstance(x, dict)]))
            if dur > 0:
                # um pouco acima para evitar terminar antes do áudio por rounding
                seconds_override = max(2.0, min(20.0, (dur / n) * 1.05))
    except Exception:
        seconds_override = None

    raw_assets: List[Dict[str, Any]] = []
    for it in sorted(rows, key=lambda x: int(x.get("scene_idx", 0) or 0)):
        idx = int(it.get("scene_idx", 0) or 0)
        raw = str(it.get("image") or "").strip()
        if not raw:
            warnings.append(f"cena {idx}: image vazio")
            continue
        try:
            if raw.startswith("http://") or raw.startswith("https://"):
                lp = str(_download_media(raw, assets_dir))
            else:
                p = Path(raw).expanduser()
                if not p.is_file():
                    warnings.append(f"cena {idx}: ficheiro não encontrado")
                    continue
                lp = str(p.resolve())
            dest_name = f"scene_{idx:02d}_raw{Path(lp).suffix.lower() or '.jpg'}"
            dest = assets_dir / dest_name
            if os.path.normpath(lp) != os.path.normpath(str(dest)):
                shutil.copy2(lp, dest)
                lp = str(dest)
            raw_assets.append(
                {
                    "scene_idx": idx,
                    "local_path": lp,
                    "url": raw if raw.startswith("http") else "",
                    "source": "lab",
                    "license": "experimental",
                }
            )
        except Exception as e:
            logger.warning("[visual_agent.lab] asset cena %s: %s", idx, e)
            warnings.append(f"cena {idx}: {e}")

    if not raw_assets:
        return {
            "ok": False,
            "error": "nenhum asset válido",
            "clips": [],
            "job_path": base,
            "mode": mode_hint,
            "workflow_is_placeholder": workflow_placeholder,
            "comfy_skip_reason": comfy_skip,
            "warnings": warnings,
        }

    mp4_n = sum(1 for a in raw_assets if str(a.get("local_path") or "").lower().endswith(".mp4"))
    if mp4_n > 0:
        warnings.append(
            f"{mp4_n} cena(s) com vídeo stock (.mp4): normalização só com ffmpeg — "
            "ComfyUI/AnimateDiff só entra para imagens quando o workflow não é placeholder."
        )

    state: VideoState = {
        "channel_niche": "lab",
        "job_path": base,
        "topic": "",
        "angle": "",
        "trending_data": {},
        "script": "",
        "scenes": [],
        "raw_assets": raw_assets,
        "clips": [],
        "audio_file": "",
        "video_file": "",
        "metadata": {},
        "thumbnail": {},
        "publish_status": None,
    }

    old_secs = os.getenv("VISUAL_FALLBACK_CLIP_SECONDS")
    if seconds_override is not None:
        os.environ["VISUAL_FALLBACK_CLIP_SECONDS"] = f"{seconds_override:.3f}"
    try:
        out = visual_agent(state, visual_use_comfy=visual_use_comfy)
    except Exception as e:
        logger.exception("[visual_agent.lab] visual_agent (batch) falhou")
        return {
            "ok": False,
            "error": str(e),
            "clips": [],
            "job_path": base,
            "mode": mode_hint,
            "workflow_is_placeholder": workflow_placeholder,
            "comfy_skip_reason": comfy_skip,
            "warnings": warnings,
        }
    finally:
        if seconds_override is not None:
            if old_secs is None:
                os.environ.pop("VISUAL_FALLBACK_CLIP_SECONDS", None)
            else:
                os.environ["VISUAL_FALLBACK_CLIP_SECONDS"] = old_secs

    clips: List[str] = [c for c in (out.get("clips") or []) if c and os.path.isfile(c) and os.path.getsize(c) > 0]
    ok = len(clips) > 0
    return {
        "ok": ok,
        "error": "" if ok else "nenhum clipe válido",
        "clips": clips,
        "job_path": base,
        "mode": mode_hint,
        "workflow_is_placeholder": workflow_placeholder,
        "comfy_skip_reason": comfy_skip,
        "warnings": warnings,
    }
