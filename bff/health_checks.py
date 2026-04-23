"""
Sondagens de disponibilidade para GET /health (Ollama, envs, imports).
Não expõe valores de segredos — apenas configurado sim/não.
"""

from __future__ import annotations

import importlib.util
import os
import time
from typing import Any, Dict

from backend.config_validation import remote_health_probe_timeout


def _masked_env_set(name: str) -> bool:
    v = (os.getenv(name) or "").strip()
    return bool(v)


def _maybe_auth_headers_for_upstream(base_url: str) -> Dict[str, str]:
    """
    Se estivermos a chamar o jwt_broker proxy (/v1/proxy/...), anexar Authorization.
    Nunca retorna o token em texto no health; só usa para a chamada HTTP.
    """
    tok = (os.getenv("WORKSHOP_ACCESS_TOKEN") or "").strip().strip('"')
    if not tok:
        return {}
    if "/v1/proxy/" not in (base_url or ""):
        return {}
    return {"Authorization": f"Bearer {tok}"}


def probe_ollama() -> Dict[str, Any]:
    base = (os.getenv("OLLAMA_BASE_URL") or "http://gpu-server-01:11434").rstrip("/")
    t0 = time.perf_counter()
    try:
        import requests

        headers = _maybe_auth_headers_for_upstream(base)
        r = requests.get(f"{base}/api/tags", timeout=3.0, headers=headers)
        ms = int((time.perf_counter() - t0) * 1000)
        ok = r.status_code == 200
        return {
            "status": "ok" if ok else "error",
            "base_url": base,
            "latency_ms": ms,
            "http_status": r.status_code,
            "detail": None if ok else (r.text[:240] if r.text else "non-200"),
        }
    except Exception as e:
        return {
            "status": "error",
            "base_url": base,
            "latency_ms": None,
            "http_status": None,
            "detail": str(e)[:400],
        }


def probe_pytrends_import() -> Dict[str, Any]:
    try:
        spec = importlib.util.find_spec("pytrends.request")
        if spec is None:
            return {"status": "error", "detail": "pacote pytrends não encontrado"}
        importlib.import_module("pytrends.request")
        return {"status": "ok", "detail": "import OK"}
    except Exception as e:
        return {"status": "error", "detail": str(e)[:400]}


def probe_youtube_config() -> Dict[str, Any]:
    ok = _masked_env_set("YOUTUBE_API_KEY")
    return {
        "status": "ok" if ok else "error",
        "configured": ok,
        "detail": None if ok else "defina YOUTUBE_API_KEY no ambiente",
    }


def probe_image_search_config() -> Dict[str, Any]:
    keys = {
        "pexels": _masked_env_set("PEXELS_API_KEY"),
        "pixabay": _masked_env_set("PIXABAY_API_KEY"),
        "unsplash": _masked_env_set("UNSPLASH_ACCESS_KEY"),
    }
    any_ok = any(keys.values())
    return {
        "status": "ok" if any_ok else "error",
        "sources": keys,
        "detail": None if any_ok else "nenhuma chave PEXELS/PIXABAY/UNSPLASH configurada",
    }


def probe_comfyui() -> Dict[str, Any]:
    base = (os.getenv("COMFYUI_BASE_URL") or "").strip().rstrip("/")
    if not base:
        return {"status": "ok", "detail": "COMFYUI_BASE_URL não definido", "skipped": True}
    t0 = time.perf_counter()
    try:
        import requests

        headers = _maybe_auth_headers_for_upstream(base)
        r = requests.get(f"{base}/system_stats", timeout=3.0, headers=headers)
        ms = int((time.perf_counter() - t0) * 1000)
        ok = r.status_code == 200
        return {
            "status": "ok" if ok else "error",
            "base_url": base,
            "latency_ms": ms,
            "http_status": r.status_code,
            "detail": None if ok else (r.text[:120] if r.text else "non-200"),
        }
    except Exception as e:
        return {
            "status": "error",
            "base_url": base,
            "latency_ms": None,
            "http_status": None,
            "detail": str(e)[:400],
        }


def probe_jwt_broker() -> Dict[str, Any]:
    url = (os.getenv("JWT_BROKER_PUBLIC_URL") or "").strip().rstrip("/")
    if not url:
        return {"status": "ok", "detail": "JWT_BROKER_PUBLIC_URL não definido", "skipped": True}
    t0 = time.perf_counter()
    try:
        import requests

        r = requests.get(f"{url}/health/live", timeout=remote_health_probe_timeout())
        ms = int((time.perf_counter() - t0) * 1000)
        ok = r.status_code == 200
        return {
            "status": "ok" if ok else "error",
            "base_url": url,
            "latency_ms": ms,
            "http_status": r.status_code,
            "detail": None if ok else (r.text[:120] if r.text else "non-200"),
        }
    except Exception as e:
        return {
            "status": "error",
            "base_url": url,
            "latency_ms": None,
            "http_status": None,
            "detail": str(e)[:400],
        }


def probe_lab_credentials_proxy() -> Dict[str, Any]:
    base = (os.getenv("LAB_CREDENTIALS_BASE_URL") or "").strip().rstrip("/")
    if not base:
        return {"status": "ok", "detail": "LAB_CREDENTIALS_BASE_URL não definido", "skipped": True}
    if not base.startswith("http"):
        base = "http://" + base.lstrip("/")
    t0 = time.perf_counter()
    try:
        import requests

        # O jwt_broker não expõe GET /; o endpoint canónico de liveness é /health/live.
        r = requests.get(f"{base}/health/live", timeout=remote_health_probe_timeout())
        ms = int((time.perf_counter() - t0) * 1000)
        ok = r.status_code == 200
        return {
            "status": "ok" if ok else "error",
            "base_url": base,
            "latency_ms": ms,
            "http_status": r.status_code,
            "detail": None if ok else (r.text[:120] if r.text else "non-200"),
        }
    except Exception as e:
        return {
            "status": "error",
            "base_url": base,
            "latency_ms": None,
            "http_status": None,
            "detail": str(e)[:400],
        }


def build_health_report() -> Dict[str, Any]:
    """Agrega todas as sondagens; não falha se uma dependência cair."""
    checks: Dict[str, Any] = {
        "ollama": probe_ollama(),
        "pytrends": probe_pytrends_import(),
        "youtube_api": probe_youtube_config(),
        "image_search_keys": probe_image_search_config(),
        # ComfyUI é um serviço "sob demanda" no workshop (e pode estar atrás de túnel/WSL).
        # Não deve degradar o health do BFF; usamos apenas em fluxos de Visual.
        "comfyui": {"status": "ok", "detail": "ignored (on-demand)", "skipped": True},
        "jwt_broker": probe_jwt_broker(),
        "lab_credentials_proxy": probe_lab_credentials_proxy(),
    }
    errors = [k for k, v in checks.items() if isinstance(v, dict) and v.get("status") == "error"]
    overall = "ok" if not errors else "degraded"
    return {
        "service": "ia_videostudio_bff",
        "status": overall,
        "checks": checks,
        "errors": errors,
    }


def overall_status_from_checks(report: Dict[str, Any]) -> str:
    return str(report.get("status") or "unknown")
