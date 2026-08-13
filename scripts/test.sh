#!/usr/bin/env bash
# Start a temporary server, run the 24-check self-test suite.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
source .venv/bin/activate

PORT="${PORT:-8092}"
if curl -s "http://127.0.0.1:$PORT/health" >/dev/null 2>&1; then
  echo "server already running on :$PORT — running self-test against it"
else
  echo "starting server on :$PORT"
  uvicorn app.main:app --host 127.0.0.1 --port "$PORT" --workers 1 > data/logs/selftest-server.log 2>&1 &
  SERVER_PID=$!
  trap "kill $SERVER_PID 2>/dev/null || true" EXIT
  for i in $(seq 1 60); do
    if curl -s "http://127.0.0.1:$PORT/ready" >/dev/null 2>&1; then break; fi
    sleep 2
  done
fi

echo "== running 24-check self test =="
python - "$PORT" <<'EOF'
import asyncio, sys
from app.tests.selftest import SelfTestRunner

async def main():
    runner = SelfTestRunner(f"http://127.0.0.1:{sys.argv[1]}")
    result = await runner.run()
    for r in result["results"]:
        mark = "PASS" if r["passed"] else "FAIL"
        print(f"[{mark}] {r['name']:24s} {r['message']}")
    print(f"\n{result['passed']}/{result['total']} PASSED")
    if result["failed"]:
        raise SystemExit(1)

asyncio.run(main())
EOF
