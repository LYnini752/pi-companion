#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
exec vendor/llama.cpp/build/bin/llama-server \
  --model models/Qwen3-0.6B-Q8_0.gguf --alias qwen3-0.6b \
  --host 127.0.0.1 --port "${PI_LLM_PORT:-8080}" \
  --ctx-size 4096 --threads "${PI_LLM_THREADS:-4}" --parallel 1 \
  --jinja --chat-template-kwargs '{"enable_thinking":false}'
