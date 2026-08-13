#!/usr/bin/env bash
# Update the app: pull code, rebuild GUI, restart service.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "== updating =="
git pull --ff-only 2>/dev/null || echo "not a git checkout; skipping pull"
source .venv/bin/activate
pip install -r requirements.txt -q
(cd web && npm install --silent && npm run build >/dev/null)
echo "== restarting service =="
if systemctl is-active --quiet magpie-tts 2>/dev/null; then
  sudo systemctl restart magpie-tts
  echo "magpie-tts restarted"
else
  echo "no systemd service; restart uvicorn manually"
fi
