#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR/web"

PORT="${PORT:-8092}"
HOST="${HOST:-0.0.0.0}"

if [[ ! -f ".env" && -f ".env.example" ]]; then
  cp ".env.example" ".env"
fi

if [[ ! -d ".venv" ]]; then
  python3 -m venv ".venv"
fi

# shellcheck source=/dev/null
source ".venv/bin/activate"

python -m pip install --upgrade pip >/dev/null

if [[ -f "../requirements.txt" ]]; then
  pip install -r "../requirements.txt"
else
  echo "ERROR: requirements.txt not found in $ROOT_DIR" >&2
  exit 1
fi

# Ensure the repo root is importable even when running from ./web
export PYTHONPATH="${ROOT_DIR}:${PYTHONPATH:-}"

exec python -m uvicorn bff.lab_server:app --host "$HOST" --port "$PORT"

