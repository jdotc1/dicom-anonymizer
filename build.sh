#!/bin/bash
set -euo pipefail
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$PROJECT_DIR/toolchain.sh"
BUILD_DIR="${BUILD_DIR:-$PROJECT_DIR/build}"
APP_PATH="$BUILD_DIR/DICOM Anonymizer 2.0.app"
mkdir -p "$APP_PATH/Contents/MacOS" "$APP_PATH/Contents/Resources"
"$SWIFT_COMPILER" "${SWIFT_FLAGS[@]}" -O \
  "$PROJECT_DIR/Sources/DICOMAnonymizerApp.swift" \
  -o "$APP_PATH/Contents/MacOS/DICOMAnonymizer2"
python3 - "$PROJECT_DIR" "$APP_PATH" <<'PY'
import json, os, pathlib, plistlib, shutil, sys
import pydicom
project, app = map(pathlib.Path, sys.argv[1:])
resources = app / 'Contents/Resources'
if pydicom.__version__ != '3.0.2':
    raise SystemExit('Build requires pydicom 3.0.2; install the pinned version from requirements.txt.')
shutil.copytree(project / 'engine', resources / 'engine', dirs_exist_ok=True, ignore=shutil.ignore_patterns('__pycache__'))
shutil.copy2(project / 'bootstrap.py', resources)
shutil.copy2(project / 'LICENSE', resources)
shutil.copy2(project / 'THIRD_PARTY_NOTICES.md', resources)
vendor = resources / 'vendor'
vendor.mkdir(exist_ok=True)
shutil.copytree(pathlib.Path(pydicom.__file__).parent, vendor / 'pydicom', dirs_exist_ok=True, ignore=shutil.ignore_patterns('__pycache__', 'test_files', 'tests', '*.dcm', '*.dicom'))
# Remove fixture payloads from an earlier incremental build as well.
for pattern in ('*.dcm', '*.dicom'):
    for fixture in (vendor / 'pydicom').rglob(pattern):
        fixture.unlink()
metadata = pathlib.Path(pydicom.__file__).parent.parent / 'pydicom-3.0.2.dist-info'
shutil.copytree(metadata, vendor / metadata.name, dirs_exist_ok=True)
(resources / 'BuildInfo.json').write_text(json.dumps({
 'xcode': os.environ['BUILD_XCODE_VERSION'],
 'swift': os.environ['BUILD_SWIFT_VERSION'],
 'macos_sdk': os.environ['BUILD_SDK_VERSION'],
 'swift_language_mode': '6', 'deployment_target': '13.0', 'architecture': 'arm64',
}, indent=2) + '\n')
info = {
 'CFBundleDevelopmentRegion':'en', 'CFBundleDisplayName':'DICOM Anonymizer 2.0',
 'CFBundleExecutable':'DICOMAnonymizer2',
 'CFBundleIdentifier':'io.github.jdotc1.dicom-anonymizer', 'CFBundleInfoDictionaryVersion':'6.0',
 'CFBundleName':'DICOM Anonymizer 2.0', 'CFBundlePackageType':'APPL',
 'CFBundleShortVersionString':'2.0', 'CFBundleVersion':'14', 'LSMinimumSystemVersion':'13.0',
 'NSHighResolutionCapable':True, 'NSPrincipalClass':'NSApplication',
}
with (app / 'Contents/Info.plist').open('wb') as f: plistlib.dump(info, f)
for cache in resources.rglob('__pycache__'):
    shutil.rmtree(cache)
print(app)
PY
python3 "$PROJECT_DIR/scripts/bundle_python.py" "$APP_PATH"
if [[ -n "${APP_ICON_RESOURCES:-}" ]]; then
  python3 "$PROJECT_DIR/scripts/apply_icon.py" "$APP_PATH" "$APP_ICON_RESOURCES"
fi
/usr/bin/codesign --force --sign - "$APP_PATH"
/usr/bin/codesign --verify --strict "$APP_PATH"
