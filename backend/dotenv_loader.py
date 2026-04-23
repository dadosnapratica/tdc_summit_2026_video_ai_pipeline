"""Carrega `.env` do pacote workshop e da raiz do monorepo (mesma ordem que o BFF)."""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv


def workshop_roots_from_here(here: Path) -> tuple[Path, Path]:
    """
    `here` deve ser um ficheiro dentro de `workshop/` (ex.: workshop/backend/foo.py).
    Devolve (pasta workshop/, raiz do monorepo).
    """
    workshop_pkg = here.resolve().parents[1]
    repo_root = here.resolve().parents[2]
    return workshop_pkg, repo_root


def load_workshop_dotenv(*, here: Path | None = None) -> None:
    """
    Prioridade: `workshop/.env` (override), depois `.env` na raiz do monorepo (sem override).
    """
    base = here if here is not None else Path(__file__).resolve()
    workshop_pkg, repo_root = workshop_roots_from_here(base)
    load_dotenv(dotenv_path=str(workshop_pkg / ".env"), override=True)
    load_dotenv(dotenv_path=str(repo_root / ".env"), override=False)
