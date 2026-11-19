import json
from pathlib import Path
import subprocess
import sys
import tempfile
import wave

import numpy as np
import pytest
import soundfile as sf

import companion
from audio_io import prepare_audio, to_mono_16k
from companion import reply, doctor, load_config, clean_answer

CONFIG = {"model": {"name": "local", "model": "small", "base_url": "http://127.0.0.1:8080/v1"},
          "whisper_cli": "/missing/whisper", "piper_cli": "/missing/piper",
          "whisper_model": "/missing/whisper.bin", "piper_model": "/missing/voice.onnx"}


def test_context_is_bounded_and_no_persona_lost():
    history = [{"role": "user" if i % 2 == 0 else "assistant", "content": str(i)} for i in range(20)]
    def fake(model, messages, **kwargs):
        assert messages[0]["role"] == "system"
        assert len(messages) == 12
        assert messages[1]["role"] == "user"
        assert messages[-1]["content"] == "你好"
        return {"text": "<think>private reasoning</think>你好，我是小派"}
    answer, updated = reply("你好", history, CONFIG, fake)
    assert answer == "你好，我是小派"
    assert len(updated) == 12
    assert len(history) == 20


def test_invalid_input_never_calls_model():
    for text in ("", "  ", "a" * 2001):
        with pytest.raises(ValueError):
            reply(text, [], CONFIG, lambda *a, **kw: pytest.fail("must not call"))
    with pytest.raises(ValueError):
        clean_answer('<think>unfinished reasoning')


def test_doctor_does_not_claim_models_exist():
    status = doctor(CONFIG)
    assert status["whisper_cli"] is False
    assert status["piper_model"] is False


def test_paths_are_relative_to_config_not_cwd(tmp_path, monkeypatch):
    folder = tmp_path / 'config'; folder.mkdir()
    d = dict(CONFIG, whisper_model='models/base.bin', piper_cli='.venv/bin/piper')
    p = folder / 'settings.json'; p.write_text(json.dumps(d))
    monkeypatch.chdir(tmp_path)
    c = load_config(p)
    assert c['whisper_model'] == str(folder / 'models/base.bin')
    assert c['piper_cli'] == str(folder / '.venv/bin/piper')


def test_stereo_48k_is_normalized_and_duration_preserved(tmp_path):
    rate = 48000
    tone = np.sin(np.arange(rate) * 2 * np.pi * 440 / rate).astype(np.float32) * .1
    source, target = tmp_path / 'stereo.wav', tmp_path / 'ready.wav'
    sf.write(source, np.column_stack([tone, tone]), rate)
    prepare_audio(source, target)
    data, out_rate = sf.read(target)
    assert out_rate == 16000 and data.ndim == 1 and len(data) == 16000
    assert np.sqrt(np.mean(data ** 2)) == pytest.approx(.0707, abs=.001)


def test_invalid_audio_is_rejected_without_engine(tmp_path):
    for data in (np.zeros(16000), np.full(16000, np.nan), np.ones(16000 * 31), np.ones(100)):
        with pytest.raises(ValueError):
            to_mono_16k(data, 16000)
    long_file = tmp_path / 'long.wav'
    sf.write(long_file, np.zeros(16000 * 31), 16000)
    with pytest.raises(ValueError, match='30 秒'):
        prepare_audio(long_file, tmp_path / 'never.wav')
    assert not (tmp_path / 'never.wav').exists()


def test_voice_turn_cleans_temp_files_on_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(tempfile, 'tempdir', str(tmp_path))
    seen = []
    def failing(path, config, directory):
        seen.append(directory)
        (directory / 'transcript.txt').write_text('sensitive text')
        raise RuntimeError('engine failed')
    monkeypatch.setattr(companion, 'transcribe', failing)
    with pytest.raises(RuntimeError):
        companion.voice_turn('any.wav', [], CONFIG)
    assert seen and not seen[0].exists()


def test_real_subprocess_boundary_writes_transcript_and_audio(tmp_path):
    # Exercise argv, file normalization, subprocess execution and output parsing.
    engine = tmp_path / 'fake-engine'
    engine.write_text('#!' + sys.executable + '\n' + '''import sys, pathlib, wave, struct
args=sys.argv[1:]
if '-otxt' in args:
    p=pathlib.Path(args[args.index('-of')+1]+'.txt');p.write_text('你好小派',encoding='utf-8')
else:
    text=sys.stdin.read()
    assert text=='你好'
    with wave.open(args[args.index('--output_file')+1],'wb') as out:
        out.setparams((1,2,22050,0,'NONE','not compressed'))
        out.writeframes(struct.pack('<h',1000)*2205)
''')
    engine.chmod(0o755)
    c = dict(CONFIG, whisper_cli=str(engine), piper_cli=str(engine))
    source = tmp_path / 'source.wav'; sf.write(source, np.ones(16000) * .1, 16000)
    work = tmp_path / 'work'; work.mkdir()
    assert companion.transcribe(source, c, work) == '你好小派'
    audio, rate = companion.synthesize('你好', c, tmp_path / 'out.wav')
    assert rate == 22050 and len(audio) == 2205


def test_engine_errors_do_not_expose_stderr_or_prompt(monkeypatch):
    def fail(*a, **kw):
        raise subprocess.CalledProcessError(1, ['private'], stderr='secret')
    monkeypatch.setattr(subprocess, 'run', fail)
    with pytest.raises(RuntimeError) as error:
        companion.run_process(['fake'], stdin='private')
    assert 'private' not in str(error.value) and 'secret' not in str(error.value)


def test_record_deadline_does_not_wait_forever_for_enter(monkeypatch):
    import audio_io
    import types
    samples = np.ones((48000, 1), dtype=np.float32) * .1
    class Stream:
        active = True
        def __init__(self, **kw):
            self.callback = kw['callback']
        def __enter__(self):
            self.callback(samples, len(samples), None, None)
            return self
        def __exit__(self, *args):
            self.active = False
    fake = types.SimpleNamespace(query_devices=lambda *a: {'default_samplerate':48000}, InputStream=Stream, PortAudioError=RuntimeError)
    monkeypatch.setitem(sys.modules, 'sounddevice', fake)
    ticks = iter([0, 10, 20, 31])
    monkeypatch.setattr(audio_io.time, 'monotonic', lambda: next(ticks))
    monkeypatch.setattr(audio_io.select, 'select', lambda *a: ([], [], []))
    result = audio_io.record(status=lambda x: None)
    assert len(result) == 16000


def test_audio_device_failure_has_actionable_error(monkeypatch):
    import audio_io
    import types
    class DeviceError(Exception):
        pass
    def fail(*a):
        raise DeviceError('backend internals')
    monkeypatch.setitem(sys.modules, 'sounddevice', types.SimpleNamespace(query_devices=fail, PortAudioError=DeviceError))
    with pytest.raises(RuntimeError, match='--devices'):
        audio_io.record(status=lambda x: None)


def test_python_asr_adapter_does_not_need_executable_bit(tmp_path):
    script = tmp_path / 'worker.py'; script.write_text('pass'); script.chmod(0o644)
    assert doctor(dict(CONFIG, whisper_cli=str(script)))['whisper_cli'] is True
