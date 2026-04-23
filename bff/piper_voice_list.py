"""Lista de vozes Piper para o lab: catálogo HF (tts_experiments) + scan de PIPER_VOICES_DIR."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _catalog_path() -> Path:
    return _repo_root() / "workshop" / "tts_experiments" / "data" / "piper_hf_voice_catalog.json"


def _load_catalog() -> List[Dict[str, Any]]:
    p = _catalog_path()
    if not p.is_file():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _voices_dir_from_env() -> Optional[Path]:
    raw = (os.getenv("PIPER_VOICES_DIR") or "").strip()
    if not raw:
        return None
    p = Path(raw)
    return p.resolve() if p.is_absolute() else (_repo_root() / p).resolve()


def _derive_scan_root_from_piper_model_env() -> Optional[Path]:
    """
    Se PIPER_VOICES_DIR não está definido, infere a pasta que contém todas as vozes a partir de PIPER_MODEL:
    layout típico .../piper/pt_BR-faber-medium/pt_BR-faber-medium.onnx → raiz = .../piper (irmãos = outras vozes).
    Layout plano .../voices/pt_BR-faber-medium.onnx → raiz = .../voices.
    """
    env_model = (os.getenv("PIPER_MODEL") or "").strip()
    if not env_model:
        return None
    ep = Path(env_model)
    ep = ep.resolve() if ep.is_absolute() else (_repo_root() / ep).resolve()
    if not ep.is_file():
        return None
    parent = ep.parent
    if parent.name == ep.stem:
        return parent.parent
    return parent


def _piper_scan_root() -> Optional[Path]:
    """Diretório a varrer por *.onnx (não recursivo só no nome: usa rglob)."""
    explicit = _voices_dir_from_env()
    if explicit and explicit.is_dir():
        return explicit
    return _derive_scan_root_from_piper_model_env()


def build_piper_model_options() -> Tuple[List[Dict[str, str]], Dict[str, Any]]:
    """
    Devolve (models, meta) onde cada model é {"value": path .onnx absoluto, "label": str}.
    Só inclui vozes com ficheiro `.onnx` presente (e idealmente `.onnx.json` junto — aviso se faltar).
    """
    catalog = _load_catalog()
    label_by_id: Dict[str, str] = {}
    for e in catalog:
        vid = str(e.get("id") or "").strip()
        if not vid:
            continue
        label = str(e.get("label") or vid).strip()
        label_by_id[vid] = label

    voices_dir_explicit = _voices_dir_from_env()
    scan_root = _piper_scan_root()
    seen_paths: set[str] = set()
    out: List[Dict[str, str]] = []

    if scan_root and scan_root.is_dir():
        for onnx in sorted(scan_root.rglob("*.onnx")):
            ap = str(onnx.resolve())
            if ap in seen_paths:
                continue
            seen_paths.add(ap)
            stem = onnx.stem
            label = label_by_id.get(stem) or f"{stem} (local)"
            json_side = onnx.with_suffix(".onnx.json")
            if not json_side.is_file():
                label = f"{label} · falta .json"
            out.append({"value": ap, "label": label})

    # Fallback: PIPER_MODEL aponta para um ficheiro fora do scan (ex.: path noutro disco)
    env_model = (os.getenv("PIPER_MODEL") or "").strip()
    if env_model:
        ep = Path(env_model)
        ep = ep.resolve() if ep.is_absolute() else (_repo_root() / ep).resolve()
        if ep.is_file() and str(ep) not in seen_paths:
            stem = ep.stem
            label = label_by_id.get(stem) or ep.name
            out.insert(0, {"value": str(ep), "label": label})

    env_exe = (os.getenv("PIPER_EXECUTABLE") or "").strip()
    meta = {
        "PIPER_VOICES_DIR": str(voices_dir_explicit) if voices_dir_explicit else "",
        "piper_scan_root": str(scan_root) if scan_root else "",
        "catalog_path": str(_catalog_path()),
    }
    return out, {"env": {"PIPER_EXECUTABLE": env_exe, "PIPER_MODEL": env_model}, **meta}


def resolve_piper_model_for_request(raw: Optional[str]) -> str:
    """Resolve `piper_model` do pedido para caminho absoluto `.onnx` existente."""
    if not raw or not str(raw).strip():
        raise ValueError("piper_model vazio")
    s = str(raw).strip()
    p = Path(s)
    if p.is_file() and p.suffix.lower() == ".onnx":
        return str(p.resolve())
    scan_root = _piper_scan_root()
    if scan_root and scan_root.is_dir():
        cand = (scan_root / s).resolve()
        if cand.is_file() and cand.suffix.lower() == ".onnx":
            return str(cand)
        cand2 = (scan_root / f"{s}.onnx").resolve()
        if cand2.is_file():
            return str(cand2)
        base = s.strip().replace("\\", "/").split("/")[-1]
        for onnx in scan_root.rglob("*.onnx"):
            if onnx.name == base or onnx.stem == base or str(onnx.resolve()) == s:
                return str(onnx.resolve())
    raise ValueError(f"Modelo Piper não encontrado: {s}")
