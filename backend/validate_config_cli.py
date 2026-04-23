"""
Utilitário do pacote workshop para validar variáveis de ambiente (paths, URLs).

Uso (cwd = raiz do monorepo; PYTHONPATH deve incluir a raiz):

    python -m workshop.backend.validate_config_cli
    python -m workshop.backend.validate_config_cli --strict

Equivalente legado: ``scripts/validate_workshop_config.py`` (delega para este módulo).

Para sondagens HTTP legíveis (broker, Ollama, ComfyUI, upload opcional), ver
``python -m workshop.backend.remote_services_probe`` e
``workshop/docs/CONFIGURATION.md`` (secção «Validação remota»).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from workshop.backend.config_validation import validate_workshop_configuration
    from workshop.backend.dotenv_loader import load_workshop_dotenv

    load_workshop_dotenv(here=Path(__file__).resolve())

    ap = argparse.ArgumentParser(
        description="Validar env do workshop (warnings não falham por defeito).",
        prog="python -m workshop.backend.validate_config_cli",
    )
    ap.add_argument(
        "--strict",
        action="store_true",
        help="Exit 1 também se existir algum warning.",
    )
    args = ap.parse_args(argv)

    report = validate_workshop_configuration()
    print(json.dumps(report, ensure_ascii=False, indent=2))

    counts = report.get("counts") or {}
    errs = int(counts.get("error") or 0)
    warns = int(counts.get("warning") or 0)
    if errs > 0:
        return 1
    if args.strict and warns > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
