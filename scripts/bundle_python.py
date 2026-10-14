"""Bundle pinned relocatable CPython, reusing an unchanged archive receipt."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tarfile
import tempfile
import urllib.request

project = Path(__file__).resolve().parent.parent
spec = json.loads((project / 'scripts/python-runtime.json').read_text())
cache = project / 'build/runtime-cache'
cache.mkdir(parents=True, exist_ok=True)
archive = cache / 'python.tar.gz'
receipt = cache / 'verified.json'
if not archive.exists():
    with urllib.request.urlopen(spec['url']) as response, archive.open('wb') as output:
        shutil.copyfileobj(response, output)
stat = archive.stat()
expected = {'sha256': spec['sha256'], 'size': stat.st_size, 'mtime_ns': stat.st_mtime_ns}
try:
    reusable = json.loads(receipt.read_text()) == expected
except (OSError, ValueError):
    reusable = False
if not reusable:
    with archive.open('rb') as stream:
        digest = hashlib.sha256()
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    if digest.hexdigest() != spec['sha256']:
        raise SystemExit('Pinned Python archive digest mismatch; refusing to bundle.')
    receipt.write_text(json.dumps(expected) + '\n')
resources = Path(sys.argv[1]) / 'Contents/Resources'
runtime = resources / 'python'
with tempfile.TemporaryDirectory(dir=cache) as temporary:
    # data filter rejects traversal, external links and special device entries.
    with tarfile.open(archive) as package:
        package.extractall(temporary, filter='data')
    if runtime.exists():
        shutil.rmtree(runtime)
    shutil.copytree(Path(temporary) / 'python', runtime, symlinks=True)
shutil.copytree(project / spec['license_directory'], resources / 'Python-Licenses', dirs_exist_ok=True)
shutil.copy2(project / 'scripts/python-runtime.json', resources / 'PythonRuntime.json')
info_path = resources / 'BuildInfo.json'
info = json.loads(info_path.read_text())
info['bundled_python'] = {'version': spec['version'], 'distribution': 'python-build-standalone',
                          'release': spec['release'], 'target': spec['target']}
info_path.write_text(json.dumps(info, indent=2) + '\n')
print('Bundled CPython ' + spec['version'] + (' (archive verification receipt reused)' if reusable else ' (archive verified)'))
