#!/usr/bin/env bash
# Benchmark suite: FP32 / FP16 / BF16 across English, Hindi, Hinglish.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
source .venv/bin/activate

PORT="${PORT:-8092}"
BASE="http://127.0.0.1:$PORT"
OUT="data/benchmark/$(date +%Y%m%d-%H%M%S).json"

echo "== benchmark against $BASE =="
python - "$BASE" "$OUT" <<'EOF'
import asyncio, json, sys, time
import httpx

BASE, OUT = sys.argv[1], sys.argv[2]

async def main():
    results = []
    async with httpx.AsyncClient(timeout=600) as client:
        st = (await client.get(f"{BASE}/api/profiles")).json()
        active = st["current"]
        for profile in st["data"]:
            if profile["id"] not in ("fp32-reference", "fp16-realtime", "bf16"):
                continue
            if profile["id"] != active:
                r = await client.post(f"{BASE}/api/profiles/switch", json={"profile": profile["id"]})
                if r.status_code != 200:
                    results.append({"profile": profile["id"], "error": r.text[:200]})
                    continue
            for lang, name in [("en", "English"), ("hi", "Hindi"), ("hi", "Hinglish")]:
                texts = ["Your order has already been dispatched."] if lang == "en" else \
                    ["नमस्ते सर, मैं आपकी कैसे सहायता कर सकता हूँ?"] if name == "Hindi" else \
                    ["Sir आपका order dispatch हो चुका है।"]
                r = await client.post(f"{BASE}/api/benchmark", json={
                    "profile": profile["id"], "concurrent_users": 1, "language": lang,
                    "iterations": 20, "streaming": False, "texts": texts})
                if r.status_code == 200:
                    results.append(r.json())
                else:
                    results.append({"profile": profile["id"], "language": lang, "error": r.text[:200]})
    with open(OUT, "w") as f:
        json.dump(results, f, indent=2)
    for x in results:
        if "error" in x:
            print("ERR", x["profile"], x.get("language"), x["error"])
        else:
            print(f"{x['profile']:16s} {x['language']:8s} "
                  f"TTFA p50={x['ttfa_p50_ms']:.0f}ms p95={x['ttfa_p95_ms']:.0f}ms "
                  f"RTF={x['rtf']:.3f} VRAM={x['peak_vram_mb']:.0f}MB "
                  f"req/s={x['requests_per_sec']:.1f} failures={x['failures']}")
    print("\nresults ->", OUT)

asyncio.run(main())
EOF
