"""Half-duplex local voice companion: Whisper -> Chat Completions -> Piper."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import sys
import subprocess
import tempfile
import time

from provider import chat, validate_model
from audio_io import prepare_audio, record, play

ROOT = Path(__file__).resolve().parent


def load_config(path):
    path = Path(path).expanduser().resolve()
    config = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError("配置必须是 JSON 对象")
    validate_model(config.get("model"))
    for name in ("whisper_cli", "whisper_model", "piper_cli", "piper_model"):
        value = config.get(name)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Missing {name}")
        p = Path(value).expanduser()
        if name.endswith("model") or "/" in value or value.startswith("."):
            config[name] = str(p if p.is_absolute() else path.parent / p)
    if not isinstance(config.get("persona", ""), str):
        raise ValueError("persona 必须是文本")
    language = config.get("language", "zh")
    if not isinstance(language, str) or not re.fullmatch(r"[a-z]{2,3}|auto", language):
        raise ValueError("language 必须是 Whisper 语言代码")
    return config


def executable(name):
    path = Path(name).expanduser()
    return str(path.resolve()) if path.is_file() and os.access(path, os.X_OK) else shutil.which(name)


def doctor(config):
    result = {}
    for key in ("whisper_cli", "piper_cli"):
        result[key] = (Path(config[key]).is_file() if key == "whisper_cli" and config[key].endswith(".py")
                       else bool(executable(config[key])))
    for key in ("whisper_model", "piper_model"):
        result[key] = Path(config[key]).is_file()
    result["piper_voice_config"] = Path(config["piper_model"] + ".json").is_file()
    result["model_endpoint"] = config["model"]["base_url"]
    result["note"] = "只检查文件；未打开麦克风、未请求模型、未验证树莓派硬件。"
    return result


def run_process(args, *, stdin=None):
    try:
        subprocess.run(args, input=stdin, text=True, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, check=True, timeout=180)
    except subprocess.TimeoutExpired:
        raise RuntimeError("语音引擎超时（180 秒）") from None
    except (subprocess.CalledProcessError, OSError):
        raise RuntimeError("语音引擎失败，请检查 doctor、模型兼容性和安装文档") from None


def transcribe(audio_path, config, directory):
    normalized = directory / "input-16k.wav"
    prepare_audio(audio_path, normalized)
    prefix = directory / "transcript"
    command = ([sys.executable, config["whisper_cli"]] if config["whisper_cli"].endswith(".py")
               else [executable(config["whisper_cli"]) or config["whisper_cli"]])
    run_process(command + ["-m", config["whisper_model"], "-f", str(normalized),
                 "-l", config.get("language", "zh"), "-otxt", "-of", str(prefix),
                 "-t", "4", "-nt"])
    text = prefix.with_suffix(".txt").read_text(encoding="utf-8").strip()
    if not text or not re.search(r"[\w\u4e00-\u9fff]", text):
        raise ValueError("没有识别到文字")
    return text


def clean_answer(text):
    # Reasoning is not spoken. An unterminated block must not leak into TTS.
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()
    if "<think>" in text or "</think>" in text:
        raise ValueError("模型返回了未完成的思考内容，请关闭 thinking 模式")
    if not text or len(text) > 4000:
        raise ValueError("模型回复为空或过长")
    return text


def reply(text, history, config, call=chat):
    if not isinstance(text, str) or not text.strip() or len(text) > 2000:
        raise ValueError("输入需要 1–2000 个字符")
    persona = config.get("persona", "你是友善的桌面 AI 伙伴，用简洁中文回答。")
    previous = list(history[-10:])  # five previous turns + this one = six turns
    messages = [{"role": "system", "content": persona}] + previous + [{"role": "user", "content": text}]
    response = call(config["model"], messages, max_tokens=300, temperature=0.5)
    answer = clean_answer(response["text"])
    return answer, previous + [{"role": "user", "content": text}, {"role": "assistant", "content": answer}]


def synthesize(text, config, path):
    run_process([executable(config["piper_cli"]) or config["piper_cli"],
                 "--model", config["piper_model"], "--output_file", str(path)], stdin=text)
    import soundfile as sf
    import numpy as np
    audio, rate = sf.read(path, dtype="float32")
    if not audio.size or not np.isfinite(audio).all() or len(audio) > rate * 120:
        raise RuntimeError("语音合成没有产生有效、长度合理的音频")
    return audio, rate


def voice_turn(audio_path, history, config, status=print):
    timings = {}
    with tempfile.TemporaryDirectory(prefix="pi-companion-") as temp:
        directory = Path(temp)
        start = time.monotonic()
        status("识别中")
        text = transcribe(audio_path, config, directory)
        timings["asr_seconds"] = round(time.monotonic()-start, 3)
        start = time.monotonic()
        status("思考中")
        answer, updated = reply(text, history, config)
        timings["llm_seconds"] = round(time.monotonic()-start, 3)
        start = time.monotonic()
        status("合成中")
        audio, rate = synthesize(answer, config, directory / "reply.wav")
        timings["tts_seconds"] = round(time.monotonic()-start, 3)
        return text, answer, updated, audio, rate, timings


def microphone_turn(history, config, released=None, status=print):
    import soundfile as sf
    audio = record(config.get("input_device"), released, status)
    with tempfile.TemporaryDirectory(prefix="pi-recording-") as temp:
        wav = Path(temp) / "input.wav"
        sf.write(wav, audio, 16000, subtype="PCM_16")
        return voice_turn(wav, history, config, status)


def gpio_loop(config, button_pin, led_pin):
    from gpiozero import Button, LED
    if button_pin == led_pin or not all(2 <= x <= 27 for x in (button_pin, led_pin)):
        raise ValueError("按钮和 LED 必须使用不同的 BCM 2–27 引脚")
    history = []
    # Pins are touched only when --gpio is explicitly selected.
    with Button(button_pin, pull_up=True, bounce_time=0.05) as button, LED(led_pin) as led:
        print("GPIO 模式就绪：按住按钮说话；Ctrl+C 退出。仅日志状态，不记录对话。", flush=True)
        while True:
            button.wait_for_press()
            led.on()
            def status(message):
                print(message, flush=True)
                if message != "正在录音，松开按钮 / 按 Enter 结束（最多 30 秒）":
                    led.blink(on_time=0.15, off_time=0.15)
            try:
                _, _, updated, audio, rate, _ = microphone_turn(
                    history, config, lambda: not button.is_pressed, status)
                play(audio, rate, config.get("output_device"))
                history = updated
            except (RuntimeError, ValueError, OSError) as exc:
                print(f"本轮失败：{exc}", flush=True)
            finally:
                led.off()
            # Long presses do not start a second recording when the 30s cap fires.
            button.wait_for_release()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(ROOT / "config.local.json"))
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--doctor", action="store_true")
    modes.add_argument("--devices", action="store_true")
    modes.add_argument("--text", action="store_true", help="交互式纯文字对话")
    modes.add_argument("--prompt", help="单次文字对话，不录音、不播放")
    modes.add_argument("--audio", help="WAV/FLAC/OGG 文件，0.2–30 秒；不打开麦克风")
    modes.add_argument("--gpio", action="store_true", help="树莓派按钮录音模式")
    parser.add_argument("--output", help="与 --audio 搭配，保存回复 WAV；不播放")
    parser.add_argument("--button-pin", type=int, default=17)
    parser.add_argument("--led-pin", type=int, default=27)
    args = parser.parse_args()
    if bool(args.audio) != bool(args.output):
        parser.error("--audio 和 --output 必须一起使用")
    if args.devices:
        import sounddevice as sd
        print(sd.query_devices())
        return
    config = load_config(args.config)
    if args.doctor:
        checks = doctor(config)
        print(json.dumps(checks, ensure_ascii=False, indent=2))
        if any(value is False for value in checks.values()):
            raise SystemExit(1)
        return
    if args.prompt is not None:
        print(reply(args.prompt, [], config)[0])
        return
    if not args.text:
        missing = [k for k, v in doctor(config).items() if v is False]
        if missing:
            raise ValueError("缺少组件：" + ", ".join(missing))
    if args.audio:
        import soundfile as sf
        text, answer, _, audio, rate, timings = voice_turn(args.audio, [], config)
        destination = Path(args.output).expanduser()
        destination.parent.mkdir(parents=True, exist_ok=True)
        sf.write(destination, audio, rate, format="WAV", subtype="PCM_16")
        print(json.dumps({"transcript": text, "answer": answer, "output": str(destination),
                          "timings": timings}, ensure_ascii=False, indent=2))
        return
    if args.gpio:
        gpio_loop(config, args.button_pin, args.led_pin)
        return
    history = []
    print("Pi Companion · /quit 退出 · /reset 清空对话。语音处理中会写临时文件，正常退出后删除。")
    while True:
        command = input("输入文字：" if args.text else "Enter 开始说话：")
        if command == "/quit":
            break
        if command == "/reset":
            history = []
            continue
        try:
            if args.text:
                answer, history = reply(command, history, config)
                print(answer)
            else:
                text, answer, updated, output, rate, timing = microphone_turn(history, config)
                print(f"你：{text}\n伙伴：{answer}\n耗时：{timing}")
                play(output, rate, config.get("output_device"))
                history = updated
        except (RuntimeError, ValueError, OSError) as exc:
            print(f"本轮失败：{exc}")


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\n已退出")
    except (RuntimeError, ValueError, OSError, ImportError) as exc:
        raise SystemExit(f"启动失败：{exc}") from None
