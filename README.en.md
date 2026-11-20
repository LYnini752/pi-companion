# Pi Companion

[中文](README.md) · An open-source voice companion for a Raspberry Pi inside a removable desk or toy enclosure.

Hold a button to speak, release it, then hear a response. The default stack runs locally: **Whisper.cpp → Qwen3-0.6B → Piper**. Keyboard and audio-file modes let you try the software on a computer before buying or wiring hardware.

**Software alpha.** Real model inference has passed on macOS ARM64 and a GitHub-hosted Linux ARM64 runner. No Raspberry Pi board, microphone, speaker, GPIO wiring, enclosure, or battery has been tested. See [the validation record, including failures](VALIDATION.md).

## Quick start

Target: Raspberry Pi 4/5 with a 64-bit Linux OS, not a Pico microcontroller. On Raspberry Pi OS, install system prerequisites:

```bash
sudo apt update
sudo apt install -y git curl build-essential libportaudio2 libsndfile1 pkg-config
```

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then:

```bash
git clone https://github.com/LYnini752/pi-companion.git
cd pi-companion
bash scripts/setup.sh
.venv/bin/python scripts/download_models.py
```

The installer creates a local Python 3.10 environment, builds a pinned llama.cpp source distribution, and preserves an existing `config.local.json`. Model downloads are revision-pinned and SHA-256 checked. Model files occupy approximately 850 MB; compilation and dependencies need additional space.

Supply a Piper voice you have permission to use, setting `piper_model` in `config.local.json` to its `.onnx` path, with the matching `.onnx.json` beside it. The sample Chinese huayan voice has **Unknown dataset licensing** in its model card. It is not bundled or commercially cleared. If you understand that limitation and want the local evaluation example:

```bash
.venv/bin/python scripts/download_models.py --include-demo-voice
```

Start the local LLM in one terminal:

```bash
bash scripts/serve_llm.sh
```

In another terminal:

```bash
.venv/bin/python companion.py --doctor
.venv/bin/python scripts/demo.py
```

The demo generates a synthetic question, recognizes it, gets a model response, and writes `.local/demo/reply.wav` plus `run.json`. It does not open a microphone or play audio.

For your own audio or an interactive conversation:

```bash
.venv/bin/python companion.py --audio question.wav --output reply.wav
.venv/bin/python companion.py --devices
.venv/bin/python companion.py
```

Press Enter to start/stop recording; recording stops after 30 seconds. `/quit` exits, `/reset` clears conversation history, and `--text` enables text-only chat. File inputs must be 0.2–30 seconds, at most 30 MB; WAV/FLAC/OGG are supported. Device-native sample rates are converted automatically.

## Button and enclosure

Read [HARDWARE.md](HARDWARE.md) before wiring. Defaults use BCM17 for a momentary button to ground, and BCM27 for an LED with a 330 Ω series resistor. Disconnect power before wiring; GPIO is 3.3 V logic. A Raspberry Pi is a Linux computer, so leave ventilation and service access in any enclosure.

```bash
uv pip install --python .venv/bin/python gpiozero==2.0.1 lgpio==0.2.2.0
.venv/bin/python companion.py --gpio
```

The LED is on while recording and blinks during processing. Audio input is disabled while answering. `systemd/` contains optional templates for installation **after manual hardware verification**; they assume `/home/<username>/pi-companion`. No service is installed automatically. No validated CAD files, motor control, or battery assembly are included.

## Data and limitations

Default inference is local. Installation downloads software/models. If you replace the model configuration with a remote HTTPS Chat Completions endpoint, transcripts, persona, and recent dialogue are sent there. API keys belong in an environment variable referenced by `api_key_env`, never in committed configuration.

At most six turns are retained in memory, with a conservative 3000-byte UTF-8 content budget. Temporary speech files are deleted on normal completion or handled exceptions; sudden termination may leave temporary files. Explicit output files remain on disk.

ASR can mishear names and longer sentences; the small LLM can invent answers. A recorded 15-second test failed semantically despite completing the pipeline. This is an interaction demo, not an accuracy-validated assistant. Cloud ARM64 timings do not predict Raspberry Pi performance. Voice licensing and physical product validation remain separate requirements for any future kit.

## Checks and license

```bash
uv pip install --python .venv/bin/python pytest gpiozero==2.0.1
.venv/bin/python -m pytest -q
```

CI runs core tests, Linux x86_64/ARM64 builds, and real model inference on ARM64. Tests do not establish electrical or audio-device compatibility.

Project code: GPL-3.0. Third-party software and separately downloaded models retain their own licenses; see [THIRD_PARTY.md](THIRD_PARTY.md).

## Included samples

See [sample data and attribution](examples/README.md) for ready-to-use inputs, offline previews, licenses, and limitations. No API credentials are included.
