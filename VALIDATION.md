# Validation record

Development machine: macOS ARM64, Apple M4, 16 GB RAM. Python 3.10.22 in a project-local virtual environment. No Raspberry Pi, GPIO button, microphone capture or speaker playback has been tested in this session.

## Completed

- 25 core tests passed: bounded history, reasoning-block handling, relative paths, stereo 48 kHz conversion, silence/NaN/length rejection, temporary-file cleanup, real subprocess boundary with deterministic fake engines, HTTP request/response protocol, redirect refusal, redacted errors and configuration constraints, source extraction checks and GPIO Zero mock-pin control flow (success/failure cleanup).
- Real Piper 1.3.0 / huayan medium inference generated a 22,050 Hz WAV of 2.519 seconds from Chinese test text. The file was generated without microphone input or speaker playback.
- Qwen GGUF, Whisper base and Piper voice/config downloads verified against pinned SHA-256 values in `models.json`.

## Real local model round trip

- Input: synthetic Chinese sentence generated locally by Piper, 2.519 seconds. No human voice recording was used.
- Whisper base transcription: `你好小拍請用一句話介紹自己` (the intended name 小派 was misrecognized as 小拍).
- Qwen response: `你好！我是小派，一个温和好奇的桌面AI伙伴。`
- First run: ASR 8.402 s, LLM 0.478 s, TTS 1.913 s.
- Fresh Python environment run, concurrent system load: ASR 23.989 s, LLM 0.947 s, TTS 3.471 s. These observations are not controlled performance benchmarks or Raspberry Pi estimates.
- Second independent synthetic prompt about finishing tennis training was transcribed accurately and produced a short reply; observed ASR 2.684 s / LLM 1.074 s / TTS 1.275 s. No human listening assessment was performed.
- Real two-turn text memory check: after saying the user likes tennis, the follow-up returned `网球。`.
- One-command synthetic demo (`scripts/demo.py`) generated its own short question and saved a valid reply WAV; observed ASR 1.643 s / LLM 0.189 s / TTS 1.113 s after switching the ASR worker to beam search with a general simplified-Chinese prompt.
- **Failed longer-prompt quality case:** a 15.000-second synthetic sentence described walking and tennis. Whisper misheard `先散步` as `现三波`; Qwen did not recover the intended answer and in one run invented table tennis. Beam search did not resolve this. The pipeline completed, but semantic accuracy failed. This is a demo of interaction, not a validated factual assistant. A persona instruction cannot guarantee prevention of hallucinations.
- Silent-audio CLI check returned a clear error and did not write a reply file. File mode also refuses to overwrite its input, including a different path that is a hard link to the same file.
- A clean source extraction from the SHA-256 checked llama-cpp-python 0.3.16 sdist successfully built `llama-server` on macOS. Its bundled engine revision is 4227c9be4268ac844921b90f31595f81236bd317. The original source and fresh extraction matched file-for-file; installer rerun verified the source and completed.
- Clean project environment installed all pinned requirements successfully. Dependency resolution for Linux aarch64 / Python 3.10 with binary wheels only also succeeded. This checks availability, not execution on a Raspberry Pi.

## Linux CI

[Run 44559426263](https://github.com/LYnini752/pi-companion/actions/runs/44559426263) passed core checks, Ubuntu 24.04 x86_64 build, and Ubuntu 24.04 ARM64 build plus real voice inference. The ARM64 job downloaded and SHA-256 verified all model files, started its own local server, generated a synthetic question, produced a reply WAV, and stopped its child server.

ARM64 cloud observation: ASR 6.337 s / LLM 0.893 s / TTS 1.269 s. Reply: `你好！我是小派，一个温和、好奇的桌面AI伙伴。` The name 小派 was still misrecognized in the transcript. These are cloud-runner observations, not Raspberry Pi measurements. No audio file is uploaded as a CI artifact.

The local smoke runner also rejects an already occupied port and does not terminate that listener. Repeated runs released their own server port successfully. Build metadata now explicitly uses the pinned engine revision rather than accidentally inheriting the surrounding application repository's Git revision.

## Still unverified

- Real Raspberry Pi performance, thermal behavior, supply stability, microphone/speaker compatibility, GPIO electrical wiring and systemd boot behavior.
- Voice recognition/response quality across accents, noise and long conversations. Two test prompts are not a quality benchmark.
- Any manufactured enclosure fit, battery life or commercial voice clearance.

Core tests use fake speech subprocesses and a real local HTTP fixture; they do not establish model quality or Raspberry Pi performance. Results will be updated after actual engine integration.
