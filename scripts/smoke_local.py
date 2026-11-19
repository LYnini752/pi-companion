"""Start an isolated local model server, run the synthetic demo, and stop it."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from companion import load_config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8787)
    parser.add_argument('--output-dir', default=str(ROOT / '.local/smoke'))
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error('port must be 1024–65535')
    # Refuse a port that is already occupied; only terminate our own child process.
    import socket
    with socket.socket() as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        probe.bind(('127.0.0.1', args.port))
    config = load_config(ROOT / 'config.local.json')
    config['model'] = {'name':'Local smoke test', 'model':'qwen3-0.6b',
                       'base_url':f'http://127.0.0.1:{args.port}/v1',
                       'request_options':{'chat_template_kwargs':{'enable_thinking':False}}}
    with tempfile.TemporaryDirectory(prefix='pi-smoke-') as temporary:
        folder = Path(temporary)
        settings = folder / 'config.json'; settings.write_text(json.dumps(config))
        with (folder / 'server.log').open('w+') as log:
            process = subprocess.Popen(['bash', str(ROOT / 'scripts/serve_llm.sh')],
                                       env={**os.environ, 'PI_LLM_PORT':str(args.port)},
                                       stdout=log, stderr=subprocess.STDOUT)
            try:
                deadline = time.monotonic() + 180
                while True:
                    if process.poll() is not None:
                        raise RuntimeError('Local model server exited before becoming ready')
                    try:
                        with urllib.request.urlopen(f'http://127.0.0.1:{args.port}/health', timeout=1) as response:
                            if response.status == 200:
                                break
                    except OSError:
                        pass
                    if time.monotonic() >= deadline:
                        raise RuntimeError('Local model server did not become ready within 180 seconds')
                    time.sleep(0.25)
                subprocess.run([sys.executable, str(ROOT / 'scripts/demo.py'), '--config', str(settings),
                                '--output-dir', args.output_dir], check=True, timeout=400)
            except Exception:
                log.flush(); log.seek(0)
                print(log.read()[-4000:], file=sys.stderr)
                raise
            finally:
                process.terminate()
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    process.kill(); process.wait()
    print('Owned test server stopped; no microphone or GPIO was opened.')


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, ValueError, OSError, subprocess.SubprocessError) as error:
        raise SystemExit(f'Smoke test failed: {error}') from None
