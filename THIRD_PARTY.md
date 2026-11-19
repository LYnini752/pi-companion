# Third-party components and models

No model weights or upstream engine source are committed to this repository.

| Component | Source | License / note |
| --- | --- | --- |
| Whisper.cpp via pywhispercpp 1.4.0 | https://pypi.org/project/pywhispercpp/1.4.0/ | MIT; package bundles Whisper.cpp 1.8.2; no direct CLI build required |
| Whisper base GGML | https://huggingface.co/ggerganov/whisper.cpp | OpenAI Whisper MIT; 147,951,465 bytes |
| llama.cpp | https://github.com/ggml-org/llama.cpp | MIT; revision 4227c9be4268ac844921b90f31595f81236bd317 from llama-cpp-python 0.3.16 sdist, archive SHA-256 pinned in scripts/prepare_llama.py |
| Qwen3-0.6B Q8 GGUF | https://huggingface.co/Qwen/Qwen3-0.6B-GGUF | Apache-2.0; 639,446,688 bytes |
| Piper 1.3.0 | https://github.com/OHF-Voice/piper1-gpl | GPL-3.0; uses eSpeak NG phonemization; review bundled notices when redistributing |
| huayan medium Chinese voice | https://huggingface.co/rhasspy/piper-voices/blob/04ca88f5685ca5253c701af3687e155b113bd512/zh/zh_CN/huayan/medium/MODEL_CARD | Model card states dataset license Unknown, trained from HuaYan_TTS; optional local evaluation, commercial redistribution not cleared |
| NumPy / SciPy / soundfile / sounddevice | Their PyPI project metadata and source distributions | Retain each component's license and notices when redistributing |
| gpiozero / lgpio | https://gpiozero.readthedocs.io/ and https://abyz.me.uk/lg/ | Optional GPIO dependencies; inspect their license files when packaging a device image |

Model revisions and SHA-256 values are in `models.json`. Downloading a file does not grant rights beyond the originating license. This project's GPL license covers this project's code, not all separately downloaded models. For a commercial kit, select a voice with clear permission for the intended use, preserve relevant licenses, and satisfy applicable source-distribution obligations for GPL components. This repository does not supply a pre-cleared commercial voice or a ready-to-sell hardware certification package.
