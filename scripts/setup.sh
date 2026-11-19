#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
command -v uv >/dev/null || { echo 'Install uv first: https://docs.astral.sh/uv/getting-started/installation/'; exit 1; }
command -v curl >/dev/null
if [[ ! -d .venv ]]; then uv venv --python 3.10 .venv; fi
uv pip install --python .venv/bin/python -r requirements.txt cmake==4.4.5
.venv/bin/python scripts/prepare_llama.py
.venv/bin/cmake -S vendor/llama.cpp -B vendor/llama.cpp/build \
  -DCMAKE_BUILD_TYPE=Release -DGGML_METAL=OFF -DLLAMA_CURL=OFF -DLLAMA_BUILD_TESTS=OFF
.venv/bin/cmake --build vendor/llama.cpp/build --config Release --target llama-server -j "${BUILD_JOBS:-2}"
if [[ ! -f config.local.json ]]; then cp config.example.json config.local.json; fi
echo 'Engines ready. Download models with scripts/download_models.py, then start scripts/serve_llm.sh.'
