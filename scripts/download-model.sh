#!/usr/bin/env bash
# Download the Magpie model (+ codec) into models/.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
source .venv/bin/activate

MODEL_REPO="${MAGPIE_MODEL_REPO:-nvidia/magpie_tts_multilingual_357m}"
MODEL_FILE="${MAGPIE_MODEL_FILE:-magpie_tts_multilingual_357m.nemo}"
CODEC_REPO="${MAGPIE_CODEC_REPO:-nvidia/nemo-nano-codec-22khz-1.89kbps-21.5fps}"
CODEC_FILE="${MAGPIE_CODEC_FILE:-nemo_nano_codec_22khz_1.89kbps_21.5fps.nemo}"

mkdir -p models

echo "== downloading $MODEL_REPO/$MODEL_FILE =="
python - "$MODEL_REPO" "$MODEL_FILE" <<'EOF'
import sys
from huggingface_hub import hf_hub_download
repo, fname = sys.argv[1], sys.argv[2]
path = hf_hub_download(repo_id=repo, filename=fname, local_dir="models")
print("model ->", path)
EOF

echo "== downloading codec $CODEC_REPO =="
python - "$CODEC_REPO" "$CODEC_FILE" <<'EOF'
import sys
from huggingface_hub import hf_hub_download
repo, fname = sys.argv[1], sys.argv[2]
path = hf_hub_download(repo_id=repo, filename=fname, local_dir="models")
print("codec ->", path)
EOF

ls -lh models/
echo "== download complete =="
