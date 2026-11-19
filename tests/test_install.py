import importlib.util
import io
import json
from pathlib import Path
import tarfile

import pytest

spec = importlib.util.spec_from_file_location('prepare_llama', Path(__file__).parents[1] / 'scripts/prepare_llama.py')
installer = importlib.util.module_from_spec(spec); spec.loader.exec_module(installer)


def archive(path, extra=None):
    with tarfile.open(path, 'w:gz') as output:
        entries = [('llama_cpp_python-0.3.16/vendor/llama.cpp/tools/server/server.cpp', b'int main() {}')]
        if extra:
            entries.append((extra, b'bad'))
        for name, body in entries:
            item = tarfile.TarInfo(name); item.size = len(body); output.addfile(item, io.BytesIO(body))


def test_source_extract_has_verifiable_manifest_and_detects_edits(tmp_path):
    source = tmp_path / 'source.tar.gz'; archive(source)
    dest = tmp_path / 'vendor/llama.cpp'; installer.extract(source, dest)
    baseline = json.loads((dest / '.source-files.json').read_text())
    assert baseline == installer.source_files(dest)
    (dest / 'build').mkdir(); (dest / 'build/artifact').write_text('binary')
    assert baseline == installer.source_files(dest)
    (dest / 'tools/server/server.cpp').write_text('edited')
    assert baseline != installer.source_files(dest)


def test_archive_path_traversal_is_rejected_and_not_written(tmp_path):
    source = tmp_path / 'source.tar.gz'
    archive(source, 'llama_cpp_python-0.3.16/vendor/llama.cpp/../../outside')
    dest = tmp_path / 'vendor/llama.cpp'
    with pytest.raises(ValueError, match='Unsafe'):
        installer.extract(source, dest)
    assert not dest.exists() and not (tmp_path / 'outside').exists()
