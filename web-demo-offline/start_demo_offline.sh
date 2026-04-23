#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

PORT="${PORT:-8099}"
HOST="${HOST:-0.0.0.0}"

echo "Tip: you can also run ../start_demo_offline.sh from workshop/"
echo "Serving web-demo-offline from: $ROOT_DIR"
echo "Open: http://${HOST}:${PORT}/"
echo ""

exec python3 -m http.server "$PORT" --bind "$HOST"

