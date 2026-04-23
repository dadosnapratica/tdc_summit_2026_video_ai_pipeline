"""Cliente HTTP mínimo para ComfyUI (queue + history + upload para input/)."""
from __future__ import annotations

import logging
import os
import time
import uuid
from typing import Any, Dict, List, Tuple

import requests

logger = logging.getLogger(__name__)


def upload_image_to_input(
    base_url: str,
    local_file_path: str,
    *,
    subfolder: str = "",
    overwrite: bool = True,
) -> Tuple[str, str]:
    """
    Envia uma imagem para o ComfyUI via ``POST /upload/image`` (multipart).

    Documentação upstream: servidor ``comfyanonymous/ComfyUI``, rotas ``/upload/image``.
    Campos aceites: ``image`` (ficheiro), ``type`` (input|output|temp), ``subfolder``, ``overwrite``.

    :returns: ``(filename, subfolder)`` conforme JSON da resposta — usar ``filename`` no workflow
              (Load Image usa o nome que o servidor gravou; pode diferir do original se não houver overwrite).

    """
    base_url = base_url.rstrip("/")
    fn = os.path.basename(local_file_path)
    url = f"{base_url}/upload/image"
    with open(local_file_path, "rb") as f:
        files = {"image": (fn, f, "application/octet-stream")}
        data = {
            "type": "input",
            "subfolder": subfolder or "",
            "overwrite": "true" if overwrite else "false",
        }
        r = requests.post(url, files=files, data=data, timeout=300)
    r.raise_for_status()
    js = r.json()
    name = str(js.get("name") or "").strip()
    sub = str(js.get("subfolder") or "").strip()
    if not name:
        raise RuntimeError(f"Upload sem name na resposta: {js}")
    logger.info("[comfy_client] upload/image ok name=%s subfolder=%s", name, sub)
    return name, sub


def submit_prompt(base_url: str, workflow: Dict[str, Any], *, client_id: str | None = None) -> str:
    base_url = base_url.rstrip("/")
    cid = client_id or str(uuid.uuid4())
    url = f"{base_url}/prompt"
    r = requests.post(url, json={"prompt": workflow, "client_id": cid}, timeout=60)
    r.raise_for_status()
    data = r.json()
    pid = data.get("prompt_id")
    if not pid:
        raise RuntimeError(f"Resposta sem prompt_id: {data}")
    return str(pid)


def wait_for_history(
    base_url: str,
    prompt_id: str,
    *,
    timeout_s: float = 900.0,
    poll_s: float = 1.0,
) -> Dict[str, Any]:
    base_url = base_url.rstrip("/")
    url = f"{base_url}/history/{prompt_id}"
    deadline = time.time() + timeout_s
    last_err: Exception | None = None
    while time.time() < deadline:
        try:
            r = requests.get(url, timeout=30)
            if r.status_code == 404:
                time.sleep(poll_s)
                continue
            r.raise_for_status()
            data = r.json()
            if prompt_id in data:
                return dict(data[prompt_id])
        except Exception as e:
            last_err = e
            logger.debug("[comfy_client] poll: %s", e)
        time.sleep(poll_s)
    raise TimeoutError(f"Timeout à espera do ComfyUI ({prompt_id}): {last_err}")


def collect_output_files(history_entry: Dict[str, Any]) -> List[Tuple[str, str]]:
    """
    Devolve lista de (filename, subfolder) a pedir a /view.
    Estrutura típica: history_entry['outputs'] -> node_id -> {'images':[{'filename','subfolder','type'}]}
    """
    out: List[Tuple[str, str]] = []
    outputs = history_entry.get("outputs") or {}
    if not isinstance(outputs, dict):
        return out
    for _, node_out in outputs.items():
        if not isinstance(node_out, dict):
            continue
        for im in node_out.get("images") or []:
            if not isinstance(im, dict):
                continue
            fn = str(im.get("filename") or "")
            sub = str(im.get("subfolder") or "")
            if fn:
                out.append((fn, sub))
    return out
