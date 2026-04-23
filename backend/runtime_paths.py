"""Paths estáveis para a raiz lógica do projeto (.env, `prompts/`)."""
from __future__ import annotations

from pathlib import Path


def monorepo_root() -> Path:
    """
    Diretório do monorepo (pai de `prompts/` no layout completo) ou, em pacote
    só com `workshop/`, a própria pasta workshop quando contém `workshop/prompts/`.
    Usado por `prompt_loader` para `{repo}/prompts/<agent>/`.
    """
    here = Path(__file__).resolve()
    workshop_pkg = here.parents[1]
    outer = here.parents[2]
    if (outer / "prompts").is_dir() or (outer / "requirements.txt").is_file():
        return outer
    if (workshop_pkg / "prompts").is_dir():
        return workshop_pkg
    return outer
