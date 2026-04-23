"""Validação estruturada de variáveis de ambiente do workshop (paths, URLs)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Literal, Tuple, TypedDict, Union


class CheckItem(TypedDict, total=False):
    id: str
    severity: Literal["ok", "warning", "error"]
    message: str
    detail: str


def _append(
    items: List[CheckItem],
    *,
    id_: str,
    severity: Literal["ok", "warning", "error"],
    message: str,
    detail: str = "",
) -> None:
    items.append({"id": id_, "severity": severity, "message": message, "detail": detail})


def _env(name: str) -> str:
    return (os.getenv(name) or "").strip()


def remote_health_probe_timeout() -> tuple[float, float]:
    """
    (connect, read) em segundos para GET /health/live remoto (jwt_broker, LAB_CREDENTIALS).
    O valor fixo de 3s falhava com Cloudflare/túneis lentos («Read timed out»).
    """
    try:
        c = float(os.getenv("HEALTH_REMOTE_PROBE_CONNECT_S", "4"))
    except ValueError:
        c = 4.0
    try:
        r = float(os.getenv("HEALTH_REMOTE_PROBE_READ_S", "12"))
    except ValueError:
        r = 12.0
    return (max(0.5, min(c, 60.0)), max(1.0, min(r, 120.0)))


def _check_file_optional(items: List[CheckItem], env_name: str, label: str) -> None:
    raw = _env(env_name)
    if not raw:
        return
    p = Path(raw).expanduser()
    if p.is_file():
        _append(items, id_=f"path_{env_name.lower()}", severity="ok", message=f"{label} encontrado", detail=str(p))
    else:
        _append(
            items,
            id_=f"path_{env_name.lower()}",
            severity="warning",
            message=f"{label} configurado mas ficheiro ausente",
            detail=str(p),
        )


def _auth_headers_for_upstream(base_url: str) -> Dict[str, str]:
    """Alinha ao BFF (health_checks): Bearer só para jwt_broker proxy ``/v1/proxy/``."""
    tok = (os.getenv("WORKSHOP_ACCESS_TOKEN") or "").strip().strip('"')
    if not tok or "/v1/proxy/" not in (base_url or ""):
        return {}
    return {"Authorization": f"Bearer {tok}"}


def _probe_http_get(
    url: str,
    *,
    timeout_s: Union[float, Tuple[float, float]] = 3.0,
    headers: Dict[str, str] | None = None,
) -> tuple[bool, str]:
    try:
        import requests

        r = requests.get(url, timeout=timeout_s, headers=dict(headers or {}))
        ok = 200 <= r.status_code < 300
        return ok, f"HTTP {r.status_code}"
    except Exception as e:
        return False, str(e)[:400]


def validate_workshop_configuration() -> Dict[str, Any]:
    """
    Executa verificações best-effort (não bloqueia I/O além de timeouts curtos).
    """
    items: List[CheckItem] = []

    pb = _env("PROJECT_BASE_PATH")
    if pb:
        p = Path(pb).expanduser()
        if p.is_dir():
            _append(items, id_="project_base_path", severity="ok", message="PROJECT_BASE_PATH existe", detail=str(p))
        else:
            _append(
                items,
                id_="project_base_path",
                severity="error",
                message="PROJECT_BASE_PATH definido mas não é diretório",
                detail=str(p),
            )

    pj = _env("PIPELINE_JOBS_PATH")
    if pj:
        p = Path(pj).expanduser()
        parent = p.parent
        if parent.is_dir() and os.access(parent, os.W_OK):
            _append(items, id_="pipeline_jobs_parent", severity="ok", message="pai de PIPELINE_JOBS_PATH gravável", detail=str(parent))
        elif p.is_dir() and os.access(p, os.W_OK):
            _append(items, id_="pipeline_jobs_path", severity="ok", message="PIPELINE_JOBS_PATH existe e gravável", detail=str(p))
        else:
            _append(
                items,
                id_="pipeline_jobs_path",
                severity="warning",
                message="PIPELINE_JOBS_PATH — diretório não existe ou pai não gravável",
                detail=str(p),
            )

    _check_file_optional(items, "KOKORO_MODEL", "KOKORO_MODEL")
    _check_file_optional(items, "KOKORO_VOICES", "KOKORO_VOICES")
    _check_file_optional(items, "PIPER_MODEL", "PIPER_MODEL")
    _check_file_optional(items, "PIPER_EXECUTABLE", "PIPER_EXECUTABLE")

    ollama = _env("OLLAMA_BASE_URL") or "http://gpu-server-01:11434"
    ollama = ollama.rstrip("/")
    ok_o, det_o = _probe_http_get(
        f"{ollama}/api/tags",
        headers=_auth_headers_for_upstream(ollama),
    )
    if ok_o:
        _append(items, id_="ollama_http", severity="ok", message="Ollama responde em /api/tags", detail=det_o)
    else:
        _append(
            items,
            id_="ollama_http",
            severity="warning",
            message="Ollama não alcançável (OLLAMA_BASE_URL)",
            detail=det_o,
        )

    comfy = _env("COMFYUI_BASE_URL").rstrip("/")
    if comfy:
        ok_c, det_c = _probe_http_get(
            f"{comfy}/system_stats",
            headers=_auth_headers_for_upstream(comfy),
        )
        if ok_c:
            _append(items, id_="comfyui_http", severity="ok", message="ComfyUI responde", detail=det_c)
        else:
            _append(
                items,
                id_="comfyui_http",
                severity="warning",
                message="COMFYUI_BASE_URL configurado mas host não respondeu",
                detail=det_c,
            )

    lab_base = _env("LAB_CREDENTIALS_BASE_URL").rstrip("/")
    token = _env("WORKSHOP_ACCESS_TOKEN")
    if lab_base and not token:
        _append(
            items,
            id_="proxy_credentials_token",
            severity="warning",
            message="LAB_CREDENTIALS_BASE_URL definido sem WORKSHOP_ACCESS_TOKEN",
            detail="",
        )
    if lab_base:
        # Alinhar a health_checks.probe_lab_credentials_proxy: o broker não expõe GET na raiz.
        base_norm = lab_base if lab_base.startswith("http") else f"http://{lab_base}"
        base_norm = base_norm.rstrip("/")
        ok_l, det_l = _probe_http_get(f"{base_norm}/health/live", timeout_s=remote_health_probe_timeout())
        if ok_l:
            _append(items, id_="lab_credentials_url", severity="ok", message="LAB_CREDENTIALS_BASE_URL responde", detail=det_l)
        else:
            _append(
                items,
                id_="lab_credentials_url",
                severity="warning",
                message="LAB_CREDENTIALS_BASE_URL não alcançável",
                detail=det_l,
            )

    broker = _env("JWT_BROKER_PUBLIC_URL").rstrip("/")
    if broker:
        ok_b, det_b = _probe_http_get(f"{broker}/health/live", timeout_s=remote_health_probe_timeout())
        if ok_b:
            _append(items, id_="jwt_broker_http", severity="ok", message="JWT broker /health/live OK", detail=det_b)
        else:
            _append(
                items,
                id_="jwt_broker_http",
                severity="warning",
                message="JWT_BROKER_PUBLIC_URL não alcançável",
                detail=det_b,
            )

    counts: Dict[str, int] = {"ok": 0, "warning": 0, "error": 0}
    for it in items:
        sev = it["severity"]
        counts[sev] = counts.get(sev, 0) + 1

    has_errors = counts.get("error", 0) > 0
    return {"items": items, "counts": counts, "has_errors": has_errors}
