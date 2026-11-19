"""Generate a synthetic question and run the local voice chain without audio hardware."""
import argparse
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from companion import load_config, synthesize, voice_turn


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', default=str(ROOT / 'config.local.json'))
    parser.add_argument('--output-dir', default=str(ROOT / '.local/demo'))
    args = parser.parse_args()
    config = load_config(args.config)
    destination = Path(args.output_dir).expanduser().resolve()
    destination.mkdir(parents=True, exist_ok=True)
    question = '你好小派，请用一句话介绍自己。'
    with tempfile.TemporaryDirectory(prefix='pi-demo-') as temporary:
        path = Path(temporary) / 'question.wav'
        synthesize(question, config, path)
        text, answer, _, audio, rate, timings = voice_turn(path, [], config)
    import soundfile as sf
    wav = destination / 'reply.wav'
    sf.write(wav, audio, rate, subtype='PCM_16')
    result = {'synthetic_question':question, 'transcript':text, 'answer':answer,
              'model':config['model']['model'], 'timings':timings, 'output':str(wav)}
    (destination / 'run.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print('No microphone capture or speaker playback was performed.')


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, ValueError, OSError) as error:
        raise SystemExit(f'Demo failed: {error}') from None
