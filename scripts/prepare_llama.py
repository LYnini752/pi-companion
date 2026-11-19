"""Extract the pinned llama.cpp source shipped in the upstream Python sdist."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[1]
URL = 'https://files.pythonhosted.org/packages/e4/b4/c8cd17629ced0b9644a71d399a91145aedef109c0333443bef015e45b704/llama_cpp_python-0.3.16.tar.gz'
SHA256 = '34ed0f9bd9431af045bb63d9324ae620ad0536653740e9bb163a2e1fcb973be6'
REVISION = '4227c9be4268ac844921b90f31595f81236bd317'
PREFIX = PurePosixPath('llama_cpp_python-0.3.16/vendor/llama.cpp')


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def source_files(folder):
    return {p.relative_to(folder).as_posix(): digest(p) for p in sorted(folder.rglob('*'))
            if p.is_file() and p.relative_to(folder).parts[0] not in {'build', '.source-files.json', '.source-revision'}
            and not {'.git', '__pycache__', '.pytest_cache'} & set(p.relative_to(folder).parts)}


def extract(archive, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='llama-source-', dir=destination.parent) as temporary:
        stage = Path(temporary) / 'llama.cpp'; stage.mkdir()
        with tarfile.open(archive, 'r:gz') as source:
            for member in source.getmembers():
                try:
                    relative = PurePosixPath(member.name).relative_to(PREFIX)
                except ValueError:
                    continue
                if not relative.parts or '.git' in relative.parts:
                    continue
                if '..' in relative.parts or relative.is_absolute() or member.issym() or member.islnk():
                    raise ValueError('Unsafe path or link in source archive')
                target = stage.joinpath(*relative.parts)
                if member.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                elif member.isfile():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with source.extractfile(member) as incoming, target.open('wb') as output:
                        shutil.copyfileobj(incoming, output)
        if not (stage / 'tools/server/server.cpp').is_file():
            raise ValueError('Source archive is missing llama-server')
        (stage / '.source-files.json').write_text(json.dumps(source_files(stage), indent=2))
        (stage / '.source-revision').write_text(REVISION + '\n')
        stage.rename(destination)


def main():
    destination = ROOT / 'vendor/llama.cpp'
    if destination.exists():
        marker = destination / '.source-files.json'
        if not marker.is_file() or json.loads(marker.read_text()) != source_files(destination):
            raise ValueError('Existing llama.cpp source is unverified or edited. Move it aside before rebuilding.')
        if (destination / '.source-revision').read_text().strip() != REVISION:
            raise ValueError('Source revision mismatch')
        print('Existing source verified:', REVISION)
        return
    cache = ROOT / '.local'; cache.mkdir(exist_ok=True)
    archive = cache / 'llama_cpp_python-0.3.16.tar.gz'
    if not archive.exists():
        partial = archive.with_name(archive.name + '.part')
        subprocess.run(['curl', '-L', '--fail', '--retry', '3', '--connect-timeout', '20',
                        '--max-time', '3600', '-C', '-', '-o', str(partial), URL], check=True)
        if digest(partial) != SHA256:
            raise ValueError('Source checksum mismatch; remove the partial download before retrying')
        partial.replace(archive)
    if digest(archive) != SHA256:
        raise ValueError('Cached source checksum mismatch')
    extract(archive, destination)
    print('Source extracted and verified:', REVISION)


if __name__ == '__main__':
    main()
