#!/bin/bash
set -euo pipefail
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$PROJECT_DIR/toolchain.sh"
python3 "$PROJECT_DIR/examples/generate_batch.py" --destination "$PROJECT_DIR/.synthetic/input"
TEST_APP="$PROJECT_DIR/build/DropHandlerTests.app"
mkdir -p "$TEST_APP/Contents/MacOS"
ditto "$PROJECT_DIR/build/DICOM Anonymizer 2.0.app/Contents/Resources" "$TEST_APP/Contents/Resources"
cp "$PROJECT_DIR/build/DICOM Anonymizer 2.0.app/Contents/Info.plist" "$TEST_APP/Contents/Info.plist"
# Test preferences must not share the production store.
/usr/libexec/PlistBuddy -c 'Set :CFBundleIdentifier org.example.dicomanonymizer.synthetic-tests' "$TEST_APP/Contents/Info.plist"
"$SWIFT_COMPILER" "${SWIFT_FLAGS[@]}" -D MODEL_TEST \
  "$PROJECT_DIR/Sources/DICOMAnonymizerApp.swift" "$PROJECT_DIR/UITests/DropHandlerTests.swift" \
  -o "$TEST_APP/Contents/MacOS/DICOMAnonymizer2"
"$TEST_APP/Contents/MacOS/DICOMAnonymizer2" "$PROJECT_DIR/.synthetic/input" "$PROJECT_DIR/.synthetic/native-output"
