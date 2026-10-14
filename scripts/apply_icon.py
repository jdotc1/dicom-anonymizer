"""Apply externally supplied compiled icon resources before signing the app."""
from pathlib import Path
import plistlib
import shutil
import sys

app, compiled = map(Path, sys.argv[1:])
for name in ('Assets.car', 'AppIcon.icns'):
    shutil.copy2(compiled / name, app / 'Contents/Resources' / name)
plist = app / 'Contents/Info.plist'
with plist.open('rb') as stream:
    info = plistlib.load(stream)
info['CFBundleIconName'] = 'AppIcon'
info['CFBundleIconFile'] = 'AppIcon'
with plist.open('wb') as stream:
    plistlib.dump(info, stream)
