# Magpie TTS Server — Docker image
# Build: docker build -t magpie-tts .
# Run:   docker run --gpus all -p 8092:8092 magpie-tts

FROM nvidia/cuda:12.8.0-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.10 python3.10-venv python3-pip nodejs npm ffmpeg git curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv/magpie

COPY requirements.txt pyproject.toml README.md ./
COPY app ./app
COPY configs ./configs
COPY scripts ./scripts
COPY web ./web
COPY docker/docker-entrypoint.sh ./docker-entrypoint.sh

RUN python3.10 -m venv /opt/venv && \
    /opt/venv/bin/pip install --upgrade pip -q && \
    /opt/venv/bin/pip install torch --index-url https://download.pytorch.org/whl/cu128 && \
    /opt/venv/bin/pip install "nemo_toolkit[tts]@main" kaldialign && \
    /opt/venv/bin/pip install -r requirements.txt && \
    /opt/venv/bin/pip install av && \
    (cd web && npm install --silent && npm run build) && \
    rm -rf web/node_modules

ENV PATH="/opt/venv/bin:$PATH"
EXPOSE 8092

ENTRYPOINT ["/srv/magpie/docker-entrypoint.sh"]
