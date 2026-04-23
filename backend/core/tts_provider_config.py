"""TTS_PROVIDER (CSV ou um motor) + TTS_PROVIDER_DEFAULT — lab e pipeline."""

from __future__ import annotations

import os
from typing import List

_VALID = frozenset({"kokoro", "piper"})


def _norm(s: str) -> str:
    return (s or "").strip().lower()


def tts_providers_enabled() -> List[str]:
    """
    Motores disponíveis no laboratório (dropdown / validação de API).

    - ``TTS_PROVIDER`` vazio: ``kokoro`` e ``piper`` (comportamento anterior do BFF).
    - ``TTS_PROVIDER=kokoro,piper`` (CSV): lista filtrada e sem duplicados.
    - ``TTS_PROVIDER=piper`` (um token): só esse motor (compatível com .env antigo).
    """
    raw = (os.getenv("TTS_PROVIDER") or "").strip()
    if not raw:
        return ["kokoro", "piper"]
    if "," in raw:
        out: List[str] = []
        seen = set()
        for part in raw.split(","):
            t = _norm(part)
            if t in _VALID and t not in seen:
                seen.add(t)
                out.append(t)
        return out if out else ["kokoro"]
    t = _norm(raw.split()[0] if raw else "")
    if t in _VALID:
        return [t]
    return ["kokoro"]


def tts_provider_effective() -> str:
    """
    Motor usado por ``agents.tts_agent`` e default do lab quando o pedido não envia ``provider``.

    - Com ``TTS_PROVIDER_DEFAULT`` definido e presente na lista de habilitados: usa esse.
    - Caso contrário: primeiro elemento de ``tts_providers_enabled()`` (ordem do CSV importa).
    """
    enabled = tts_providers_enabled()
    d = _norm(os.getenv("TTS_PROVIDER_DEFAULT") or "")
    if d in _VALID and d in enabled:
        return d
    return enabled[0]
