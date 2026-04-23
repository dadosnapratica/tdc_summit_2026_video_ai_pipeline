"""
Testes HTTP remotos alinhados ao workshop/.env (broker JWT, Ollama, ComfyUI).

Carrega dotenv como o BFF. Usa WORKSHOP_ACCESS_TOKEN quando COMFYUI_BASE_URL /
OLLAMA_BASE_URL contêm ``/v1/proxy/`` (jwt_broker).

Uso (na raiz do monorepo):

    python -m workshop.backend.remote_services_probe
    python -m workshop.backend.remote_services_probe --upload
    python -m workshop.backend.remote_services_probe --upload --upload-force

Documentação: ``workshop/docs/CONFIGURATION.md`` (secção «Validação remota»).

O PNG de teste é embutido no script (1x1 px); não é preciso criar ficheiro no disco como no servidor.

Se ``system_stats`` der 502, o problema é **proxy/upstream ComfyUI** (edge, túnel, serviço parado), não falta de imagem.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict

from workshop.backend.config_validation import _auth_headers_for_upstream
from workshop.backend.dotenv_loader import load_workshop_dotenv

_TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


def _get(url: str, *, headers: Dict[str, str], timeout: float) -> tuple[int, str]:
    import requests

    r = requests.get(url, headers=headers, timeout=timeout)
    tail = (r.text or "")[:200].replace("\n", " ")
    return r.status_code, tail


def _post_upload(base: str, *, headers: Dict[str, str], timeout: float) -> tuple[int, Any]:
    import requests

    base = base.rstrip("/")
    url = f"{base}/upload/image"
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        f.write(_TINY_PNG)
        path = f.name
    try:
        # multipart: não definir Content-Type manualmente (requests boundary)
        hdr = {k: v for k, v in headers.items() if k.lower() != "content-type"}
        with open(path, "rb") as fp:
            r = requests.post(
                url,
                files={"image": ("probe_remote.png", fp, "image/png")},
                data={"type": "input", "overwrite": "true"},
                headers=hdr,
                timeout=timeout,
            )
        try:
            body = r.json()
        except Exception:
            body = (r.text or "")[:500]
        return r.status_code, body
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def main(argv: list[str] | None = None) -> int:
    load_workshop_dotenv(here=Path(__file__).resolve())

    ap = argparse.ArgumentParser(description="Probes remotos com env do workshop.")
    ap.add_argument(
        "--upload",
        action="store_true",
        help="POST /upload/image (PNG mínimo embutido — mesmo critério que curl no servidor).",
    )
    ap.add_argument(
        "--upload-force",
        action="store_true",
        dest="upload_force",
        help="Com --upload: tentar POST mesmo se system_stats != 200 (diagnóstico; costuma falhar igual se o proxy dá 502).",
    )
    ap.add_argument("--timeout", type=float, default=15.0, help="Timeout HTTP (s).")
    args = ap.parse_args(argv)

    broker = (os.getenv("JWT_BROKER_PUBLIC_URL") or "").strip().rstrip("/")
    ollama = (os.getenv("OLLAMA_BASE_URL") or "").strip().rstrip("/")
    comfy = (os.getenv("COMFYUI_BASE_URL") or "").strip().rstrip("/")
    token_set = bool((os.getenv("WORKSHOP_ACCESS_TOKEN") or "").strip())

    lines: list[str] = []
    failed = False

    lines.append("=== Workshop remote probe (env: workshop/.env override, depois .env raiz) ===")
    lines.append(f"WORKSHOP_ACCESS_TOKEN: {'definido' if token_set else 'ausente'}")
    lines.append("")

    if broker:
        code, txt = _get(f"{broker}/health/live", headers={}, timeout=min(5.0, args.timeout))
        ok = code == 200
        failed |= not ok
        lines.append(f"[JWT broker] {broker}/health/live -> HTTP {code}{' OK' if ok else ' FAIL'}")
        if not ok:
            lines.append(f"  body: {txt}")
    else:
        lines.append("[JWT broker] JWT_BROKER_PUBLIC_URL vazio — skipped")

    lines.append("")

    if ollama:
        oh = _auth_headers_for_upstream(ollama)
        code, txt = _get(f"{ollama}/api/tags", headers=oh, timeout=args.timeout)
        ok = code == 200
        failed |= not ok
        lines.append(f"[Ollama] {ollama}/api/tags -> HTTP {code}{' OK' if ok else ' FAIL'}")
        if oh:
            lines.append("  (Authorization Bearer — proxy JWT)")
        if not ok:
            lines.append(f"  body: {txt}")
    else:
        lines.append("[Ollama] OLLAMA_BASE_URL vazio — skipped")

    lines.append("")

    if comfy:
        ch = _auth_headers_for_upstream(comfy)
        code, txt = _get(f"{comfy}/system_stats", headers=ch, timeout=args.timeout)
        ok = code == 200
        failed |= not ok
        lines.append(f"[ComfyUI] {comfy}/system_stats -> HTTP {code}{' OK' if ok else ' FAIL'}")
        if ch:
            lines.append("  (Authorization Bearer — proxy JWT)")
        if not ok:
            lines.append(f"  body: {txt}")

        if args.upload:
            try_upload = ok or args.upload_force
            if try_upload:
                ucode, ubody = _post_upload(comfy, headers=ch, timeout=min(120.0, args.timeout + 60))
                uok = ucode == 200 and isinstance(ubody, dict) and bool(ubody.get("name"))
                failed |= not uok
                lines.append(
                    f"[ComfyUI upload] POST /upload/image -> HTTP {ucode}{' OK' if uok else ' FAIL'}"
                )
                if not ok and args.upload_force:
                    lines.append(
                        "  (upload-forçado apesar de system_stats != 200 — esperado falhar se o proxy está em 502)"
                    )
                if isinstance(ubody, dict):
                    lines.append(f"  response: {json.dumps(ubody, ensure_ascii=False)}")
                else:
                    lines.append(f"  body: {ubody}")
            else:
                lines.append("[ComfyUI upload] não executado: system_stats tem de ser 200 primeiro.")
                lines.append(
                    "  Causa provável do teu caso: HTTP 502 no caminho jwt_broker → ComfyUI (serviço no GPU, nginx upstream, Cloudflare)."
                )
                lines.append(
                    "  Não falta gerar PNG localmente — o script já envia bytes PNG mínimos (como echo|base64 no servidor)."
                )
                lines.append("  Para tentar POST na mesma (diagnóstico): acrescente --upload-force")
    else:
        lines.append("[ComfyUI] COMFYUI_BASE_URL vazio — skipped")

    print("\n".join(lines))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
