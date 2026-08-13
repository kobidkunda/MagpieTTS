#!/usr/bin/env bash
# Magpie TTS Server — one-shot installer.
# Creates venv, installs torch (CUDA) + NeMo Speech, downloads the model,
# builds the GUI, runs the self-test, installs systemd service and starts it.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "== Magpie TTS Server install =="
echo "root: $ROOT"

# 1. dependency validation
for cmd in python3 pip3 node npm nvidia-smi; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "ERROR: required command not found: $cmd" >&2
    exit 1
  fi
done
PY_VER="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")')"
echo "python: $PY_VER"
if ! python3 -c "import sys; exit(0 if sys.version_info >= (3,10,12) else 1)"; then
  echo "ERROR: Python >= 3.10.12 required (found $PY_VER)" >&2
  exit 1
fi
if ! nvidia-smi -L >/dev/null 2>&1; then
  echo "ERROR: no NVIDIA GPU detected" >&2
  exit 1
fi

# 2. Python environment
if [ ! -d .venv ]; then
  echo "== creating venv =="
  python3 -m venv .venv
fi
source .venv/bin/activate
pip install --upgrade pip -q

# 3. PyTorch (CUDA 12.8 build; works with CUDA 13.0 drivers)
if ! python -c "import torch, torch.cuda" >/dev/null 2>&1; then
  echo "== installing PyTorch (cu128) =="
  pip install torch --index-url https://download.pytorch.org/whl/cu128
fi
python -c "import torch; print('torch', torch.__version__, 'cuda', torch.cuda.is_available())"

# 4. App deps
echo "== installing app dependencies =="
pip install fastapi "uvicorn[standard]" pydantic PyYAML numpy httpx huggingface_hub soundfile nvidia-ml-py

# 5. NeMo Speech toolkit
if ! python -c "from nemo.collections.tts.models import MagpieTTSModel" >/dev/null 2>&1; then
  echo "== installing nemo_toolkit[tts]@main (large download) =="
  pip install "nemo_toolkit[tts]@main"
  pip install kaldialign
fi

# 6. Codec dependency + transcoding
python - <<'EOF'
try:
    import av
    print("PyAV present")
except ImportError:
    print("PyAV missing: mp3/opus/flac/aac encoding will fall back to ffmpeg if installed")
EOF

# 7. Model download
bash scripts/download-model.sh

# 8. Frontend build
echo "== building frontend =="
(cd web && npm install && npm run build)

# 9. Config creation (defaults are shipped in configs/)
mkdir -p data/benchmark data/test_history data/logs models

# 10. Self-test (starts server on 8092 temporarily)
echo "== running self-test =="
bash scripts/test.sh

# 11. systemd service
echo "== installing systemd service =="
cat > /tmp/magpie-tts.service <<SVC
[Unit]
Description=Magpie TTS Server (multilingual realtime TTS, 0.0.0.0:8092)
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$ROOT
ExecStart=$ROOT/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8092 --workers 1
Restart=on-failure
RestartSec=5
Environment=CUDA_VISIBLE_DEVICES=0
LimitNOFILE=65536

[Install]
WantedBy=multi-user.target
SVC
if [ -w /etc/systemd/system ]; then
  sudo cp /tmp/magpie-tts.service /etc/systemd/system/ 2>/dev/null || cp /tmp/magpie-tts.service /etc/systemd/system/ 2>/dev/null
  sudo systemctl daemon-reload 2>/dev/null || true
  sudo systemctl enable --now magpie-tts 2>/dev/null || true
  echo "service installed: systemctl status magpie-tts"
else
  echo "WARNING: cannot write /etc/systemd/system — service file: /tmp/magpie-tts.service"
fi

echo "== install complete =="
echo "GUI:      http://<server-ip>:8092/"
echo "Swagger:  http://<server-ip>:8092/docs"
echo "Realtime: ws://<server-ip>:8092/v1/realtime?intent=synthesize"
