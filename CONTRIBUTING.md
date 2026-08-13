# Contributing to Magpie TTS Server

Thanks for your interest in contributing! This is a self-hosted, realtime,
multilingual text-to-speech API server built on NVIDIA Magpie TTS.

## How to contribute

1. **Report a bug** — open an issue with: the OS/GPU/Python versions, the exact
   request or event that failed, and the server log (`journalctl -u magpie-tts`).
2. **Propose a feature** — open an issue describing the use case and the API shape
   you would expect.
3. **Submit a pull request** — see below.

## Development setup

```bash
git clone https://github.com/kobidkunda/MagpieTTS.git
cd MagpieTTS
python3 -m venv .venv && source .venv/bin/activate
pip install torch --index-url https://download.pytorch.org/whl/cu128
pip install "nemo_toolkit[tts]@main" kaldialign
pip install -r requirements.txt
bash scripts/download-model.sh
```

Run the test suite:

```bash
.venv/bin/python -m pytest -q
```

Start a temporary server and run the full 24-check self test:

```bash
./scripts/test.sh
```

## Conventions

- The model is **shared** across all clients — never introduce multiple model
  instances or run uvicorn with more than one worker.
- Keep the OpenAI-compatible surface clean; advanced controls belong on the
  native `/api/tts/*` endpoints.
- Every endpoint must document its schema, defaults, allowed values, and examples.
- Inference changes must be validated with a warmup + self-test before they can
  become a default profile.

## Pull request checklist

- [ ] Code follows the existing style and passes `pytest`.
- [ ] New endpoints/fields are documented in `docs/API.md` or `docs/REALTIME.md`.
- [ ] No secrets, model weights, logs, or build artifacts are committed.
- [ ] The change does not increase model memory residency.

Thank you for contributing!
