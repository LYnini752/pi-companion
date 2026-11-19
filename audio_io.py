"""Bounded audio I/O; importing this module never opens a microphone."""
import math
import select
import sys
import time
from functools import wraps
from pathlib import Path

MAX_SECONDS = 30


def to_mono_16k(audio, rate):
    import numpy as np
    from scipy.signal import resample_poly
    data = np.asarray(audio, dtype=np.float32)
    if data.ndim not in (1, 2) or data.size == 0 or not np.isfinite(data).all():
        raise ValueError("音频为空或包含非有限数值")
    if not isinstance(rate, int) or not 8000 <= rate <= 192000:
        raise ValueError("音频采样率需在 8–192 kHz")
    if len(data) > rate * MAX_SECONDS:
        raise ValueError("音频不能超过 30 秒")
    if data.ndim == 2:
        if not 1 <= data.shape[1] <= 8:
            raise ValueError("音频声道数需在 1–8 之间")
        data = data.mean(axis=1)
    if len(data) < rate // 5:
        raise ValueError("音频至少需要 0.2 秒")
    if float(np.sqrt(np.mean(data.astype(np.float64) ** 2))) < 0.0001:
        raise ValueError("录音近乎静音，请检查麦克风")
    if rate != 16000:
        divisor = math.gcd(rate, 16000)
        data = resample_poly(data, 16000 // divisor, rate // divisor).astype(np.float32)
    return np.clip(data, -1, 1)


def prepare_audio(source, destination):
    import soundfile as sf
    path = Path(source)
    if path.stat().st_size > 30_000_000:
        raise ValueError("输入音频文件不能超过 30 MB")
    with sf.SoundFile(path) as audio:
        if audio.frames > audio.samplerate * MAX_SECONDS:
            raise ValueError("音频不能超过 30 秒")
        rate = int(audio.samplerate)
        data = audio.read(dtype="float32", always_2d=True)
    sf.write(destination, to_mono_16k(data, rate), 16000, subtype="PCM_16")


def device_errors(function):
    @wraps(function)
    def guarded(*args, **kwargs):
        import sounddevice as sd
        try:
            return function(*args, **kwargs)
        except sd.PortAudioError:
            raise RuntimeError("音频设备不可用，请用 --devices 检查配置、连接和权限") from None
    return guarded


@device_errors

def record(device=None, released=None, status=print):
    """Record until Enter / GPIO release / time limit. No unbounded input() wait."""
    import numpy as np
    import sounddevice as sd
    rate = int(sd.query_devices(device, "input")["default_samplerate"])
    remaining = rate * MAX_SECONDS
    chunks, errors = [], []

    def callback(data, frames, timing, state):
        nonlocal remaining
        if state:
            errors.append(str(state))
        take = min(frames, remaining)
        if take:
            chunks.append(data[:take].copy())
            remaining -= take
        if remaining <= 0:
            raise sd.CallbackStop()

    status("正在录音，松开按钮 / 按 Enter 结束（最多 30 秒）")
    with sd.InputStream(samplerate=rate, channels=1, dtype="float32", device=device,
                        callback=callback) as stream:
        deadline = time.monotonic() + MAX_SECONDS
        while stream.active and time.monotonic() < deadline:
            if released is not None:
                if released():
                    break
                time.sleep(0.03)
            elif select.select([sys.stdin], [], [], 0.05)[0]:
                line = sys.stdin.readline()
                if not line:
                    raise EOFError
                break
    if errors:
        raise RuntimeError("音频设备出现丢帧或缓冲错误；请更换设备或降低系统负载后重试")
    if not chunks:
        raise ValueError("录音为空")
    return to_mono_16k(np.concatenate(chunks), rate)


@device_errors
def play(audio, rate, device=None):
    import sounddevice as sd
    from scipy.signal import resample_poly
    target = int(sd.query_devices(device, "output")["default_samplerate"])
    if target != rate:
        divisor = math.gcd(target, rate)
        audio = resample_poly(audio, target // divisor, rate // divisor, axis=0)
    sd.play(audio, target, device=device)
    sd.wait()
