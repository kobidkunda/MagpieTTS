#!/usr/bin/env bash
# Download the model at container start if missing, then launch uvicorn.
set -euo pipefail

cd /srv/magpie

if [ ! -f models/magpie_tts_multilingual_357m.nemo ]; then
  echo "== downloading Magpie model =="
  python - <<'EOF'
from huggingface_hub import hf_hub_download
hf_hub_download(repo_id="nvidia/magpie_tts_multilingual_357m",
                filename="magpie_tts_multilingual_357m.nemo", local_dir="models")
EOF
fi

exec uvicorn app.main:app --host 0.0.0.0 --port 8092 --workers 1
