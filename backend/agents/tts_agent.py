"""tts_agent — Kokoro (preferencial), Piper (subprocess), ou WAV silencioso mínimo se nada disponível."""
from __future__ import annotations

import logging
import os
import re
import struct
import subprocess
import wave

from backend.core.state import VideoState
from backend.core.tts_provider_config import tts_provider_effective

logger = logging.getLogger(__name__)


def _apply_paragraph_pauses(text: str) -> str:
    """
    Insere uma pausa audível entre parágrafos para melhorar a cadência no TTS.
    Estratégia: ao detectar quebras de parágrafo (linhas em branco), injeta um token
    (ex.: "...") entre os blocos. Funciona para providers que recebem texto puro.
    """
    raw = (text or "").strip()
    if not raw:
        return ""
    token = (os.getenv("TTS_PARAGRAPH_PAUSE_TOKEN") or "...").strip()
    if not token:
        token = "..."
    # Normaliza quebras de linha e colapsa múltiplos "parágrafos vazios".
    s = raw.replace("\r\n", "\n").replace("\r", "\n")
    s = re.sub(r"\n{3,}", "\n\n", s)
    parts = [p.strip() for p in re.split(r"\n\s*\n", s) if p.strip()]
    if len(parts) <= 1:
        return raw
    return f"\n\n{token}\n\n".join(parts).strip()


def _write_silence_wav(path: str, *, seconds: float = 3.0, rate: int = 24000) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    nframes = int(seconds * rate)
    with wave.open(path, "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        for _ in range(nframes):
            w.writeframes(struct.pack("<h", 0))


def _tts_piper(state: VideoState, out_path: str) -> bool:
    script = (state.get("script") or "").strip()
    model = (os.getenv("PIPER_MODEL") or "pt_BR-faber-medium").strip()
    exe = (os.getenv("PIPER_EXECUTABLE") or "piper").strip()
    try:
        proc = subprocess.run(
            [exe, "--model", model, "--output_file", out_path],
            input=script.encode("utf-8"),
            capture_output=True,
            timeout=600,
        )
        return proc.returncode == 0 and os.path.isfile(out_path) and os.path.getsize(out_path) > 0
    except Exception as e:
        logger.warning("[tts_agent] Piper falhou: %s", e)
        return False


def _tts_kokoro(state: VideoState, out_path: str) -> bool:
    """Kokoro via `kokoro-onnx` — requer ONNX + ficheiro de vozes (.bin)."""
    script = (state.get("script") or "").strip()
    if not script:
        return False
    try:
        from kokoro_onnx import Kokoro  # type: ignore
        import numpy as np
    except ImportError:
        logger.info("[tts_agent] kokoro-onnx/numpy não disponível — a usar Piper/silêncio")
        return False
    model_path = (os.getenv("KOKORO_MODEL") or "").strip()
    voices_path = (os.getenv("KOKORO_VOICES") or "").strip()
    model_ok = bool(model_path) and os.path.isfile(model_path)
    voices_ok = bool(voices_path) and os.path.isfile(voices_path)
    if not model_ok or not voices_ok:
        logger.warning(
            "[tts_agent] Kokoro não configurado: "
            "KOKORO_MODEL=%r (exists=%s) KOKORO_VOICES=%r (exists=%s) cwd=%r",
            model_path,
            model_ok,
            voices_path,
            voices_ok,
            os.getcwd(),
        )
        return False
    voice = (os.getenv("KOKORO_VOICE") or "pf_dora").strip()
    lang = (os.getenv("KOKORO_LANG") or "pt").strip()
    try:
        k = Kokoro(model_path, voices_path)
        samples, sample_rate = k.create(script, voice=voice, speed=float(os.getenv("KOKORO_SPEED", "1.0")), lang=lang)
        arr = np.asarray(samples, dtype=np.float32)
        arr = np.clip(arr, -1.0, 1.0)
        pcm = (arr * 32767.0).astype(np.int16).tobytes()
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with wave.open(out_path, "w") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(int(sample_rate))
            w.writeframes(pcm)
        return os.path.isfile(out_path) and os.path.getsize(out_path) > 0
    except Exception as e:
        logger.warning("[tts_agent] Kokoro falhou: %s", e)
        return False


def tts_agent(state: VideoState) -> VideoState:
    job_path = (state.get("job_path") or "").strip()
    out_path = os.path.join(job_path, "narration.wav")
    provider = tts_provider_effective()

    # Pausas entre parágrafos (melhora prosódia no TTS)
    script = _apply_paragraph_pauses(str(state.get("script") or ""))
    state_eff: VideoState = {**state, "script": script}

    ok = False
    if provider == "kokoro":
        ok = _tts_kokoro(state_eff, out_path)
        if not ok:
            ok = _tts_piper(state_eff, out_path)
    elif provider == "piper":
        ok = _tts_piper(state_eff, out_path)
    elif provider == "comfyui_f5":
        raise NotImplementedError("comfyui_f5 reservado para nível 3 — use TTS_PROVIDER=kokoro|piper")
    else:
        ok = _tts_piper(state_eff, out_path)

    if not ok:
        est = max(3.0, min(120.0, len((script or "").split()) * 0.35))
        logger.warning("[tts_agent] fallback WAV silencioso (~%.1fs)", est)
        _write_silence_wav(out_path, seconds=est)

    return {**state, "audio_file": out_path}
