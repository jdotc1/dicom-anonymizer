#!/bin/bash
# Shared by the app and integration-test builds. Honor a per-command Xcode override.
export DEVELOPER_DIR="${DEVELOPER_DIR:-$(/usr/bin/xcode-select -p)}"
if [[ ! -d "$DEVELOPER_DIR/Platforms/MacOSX.platform" ]]; then
  echo 'A full Xcode installation is required. Set DEVELOPER_DIR to Xcode.app/Contents/Developer.' >&2
  exit 1
fi
SWIFT_COMPILER="$(/usr/bin/xcrun --toolchain XcodeDefault --sdk macosx --find swiftc)"
SDK_PATH="$(/usr/bin/xcrun --sdk macosx --show-sdk-path)"
export BUILD_SWIFT_VERSION="$("$SWIFT_COMPILER" --version)"
export BUILD_XCODE_VERSION="$(/usr/bin/xcodebuild -version)"
export BUILD_SDK_VERSION="$(/usr/bin/xcrun --sdk macosx --show-sdk-version)"
if [[ "$BUILD_SWIFT_VERSION" != *'Apple Swift version 6.4 '* ]]; then
  echo "This build requires Apple Swift 6.4 from Xcode. Selected compiler: $BUILD_SWIFT_VERSION" >&2
  exit 1
fi
SWIFT_FLAGS=(-parse-as-library -swift-version 6 -warnings-as-errors
  -sdk "$SDK_PATH" -target arm64-apple-macosx13.0
  -module-cache-path "$PROJECT_DIR/build/ModuleCache-Swift6-$BUILD_SDK_VERSION")
printf '%s\n%s\nSDK: %s; Swift language mode: 6; deployment target: macOS 13 (arm64)\n' \
  "$BUILD_XCODE_VERSION" "$BUILD_SWIFT_VERSION" "$BUILD_SDK_VERSION"
