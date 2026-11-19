"""Pinned model downloads with resume and SHA-256 verification; no bundled weights."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def fetch(item, folder):
    destination = folder / item['name']
    expected = item['sha256']
    if destination.exists():
        if digest(destination) == expected:
            print('Verified:', destination.name)
            return
        raise ValueError(f'{destination.name}: existing file checksum mismatch; move it aside before retrying')
    partial = destination.with_name(destination.name + '.part')
    url = f"https://huggingface.co/{item['repo']}/resolve/{item['revision']}/{item['path']}"
    subprocess.run(['curl', '--location', '--fail', '--retry', '3', '--connect-timeout', '20',
                    '--max-time', '3600', '--continue-at', '-', '--output', str(partial), url], check=True)
    if digest(partial) != expected:
        raise ValueError(f'{partial.name}: checksum mismatch; remove the partial file before retrying')
    partial.replace(destination)
    print('Downloaded and verified:', destination.name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--include-demo-voice', action='store_true',
                        help='Download huayan evaluation voice; dataset license is Unknown, no commercial clearance implied')
    args = parser.parse_args()
    models = ROOT / 'models'
    models.mkdir(exist_ok=True)
    for item in json.loads((ROOT / 'models.json').read_text()):
        if item['name'].startswith('zh_CN-') and not args.include_demo_voice:
            continue
        fetch(item, models)
    if not args.include_demo_voice:
        print('Voice skipped. Supply a properly licensed Piper voice or read THIRD_PARTY.md before choosing --include-demo-voice.')


if __name__ == '__main__':
    main()
