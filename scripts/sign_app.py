"""Sign nested Mach-O code before the app; credentials stay outside the source."""
from pathlib import Path
import subprocess
import sys

app = Path(sys.argv[1]).resolve()
identity = sys.argv[2]
magic = {b'\xfe\xed\xfa\xce', b'\xce\xfa\xed\xfe', b'\xfe\xed\xfa\xcf',
         b'\xcf\xfa\xed\xfe', b'\xca\xfe\xba\xbe', b'\xbe\xba\xfe\xca',
         b'\xca\xfe\xba\xbf', b'\xbf\xba\xfe\xca'}
code = []
for path in app.rglob('*'):
    if path.is_file() and not path.is_symlink():
        with path.open('rb') as stream:
            if stream.read(4) in magic:
                code.append(path)
for path in sorted(code, key=lambda p: len(p.parts), reverse=True):
    subprocess.run(['codesign', '--force', '--options', 'runtime', '--timestamp', '--sign', identity, str(path)], check=True)
subprocess.run(['codesign', '--force', '--options', 'runtime', '--timestamp', '--sign', identity, str(app)], check=True)
subprocess.run(['codesign', '--verify', '--deep', '--strict', '--verbose=2', str(app)], check=True)
print('Signed nested Mach-O files:', len(code))
