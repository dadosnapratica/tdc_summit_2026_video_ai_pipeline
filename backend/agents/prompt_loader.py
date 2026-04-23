from __future__ import annotations

from pathlib import Path

from backend.runtime_paths import monorepo_root

# workshop/backend/agents/prompt_loader.py → parents[2] == pasta workshop/
_WORKSHOP_ROOT = Path(__file__).resolve().parents[2]
_REPO_ROOT = monorepo_root()


def load_prompt(name: str) -> str:
    # Novo layout: prompts/<agent>/<name>.txt
    # Preferência: cópia auto-contida em workshop/prompts/, depois raiz do monorepo.
    if "/" in name:
        agent, fname = name.split("/", 1)
        rel = Path(agent) / f"{fname}.txt"
        for base in (_WORKSHOP_ROOT / "prompts", _REPO_ROOT / "prompts"):
            p2 = base / rel
            if p2.is_file():
                return p2.read_text(encoding="utf-8").strip()

    return ""
