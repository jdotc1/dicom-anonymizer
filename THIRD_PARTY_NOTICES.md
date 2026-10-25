# Third-party notices

The project source license is in LICENSE. That license does not replace dependency licenses or grant rights to third-party trademarks.

## pydicom

The Python engine depends on pydicom 3.0.2. The source-only repository distributes a dependency requirement rather than a vendored copy. The app build copies the installed pydicom package and its complete distribution metadata/license into the app's vendor resources, excluding upstream DICOM test/character-set/palette fixture payloads that the metadata workflow does not use. Preserve those notices whenever redistributing that package.

The upstream license is MIT-based with component-specific exceptions. Review the actual installed version's complete LICENSE and bundled notices; do not replace them with only this summary. Upstream: https://github.com/pydicom/pydicom and https://github.com/pydicom/pydicom/blob/main/LICENSE.

## Bundled Python runtime and Apple development tools

Standalone macOS releases include CPython 3.13.16 from Astral's python-build-standalone release 20261013, target aarch64-apple-darwin. The pinned install-only stripped archive and digest are recorded in `scripts/python-runtime.json`. The Python build scripts/distribution project are at https://github.com/astral-sh/python-build-standalone.

CPython and its compiled dependencies retain their own licenses. Complete upstream license texts extracted from the matching full distribution are preserved in `licenses/python-runtime/` in source and `Contents/Resources/Python-Licenses/` in the app. The runtime also retains its CPython LICENSE.txt and bundled pip/component notices. Inclusion of these notices does not relicense dependencies under the project MIT license. The matching full-distribution URL and digest are recorded alongside the runtime pin.

The runtime is copied without changing Python or dependency code and is signed for the app's distribution. Xcode, SwiftUI, AppKit, Foundation and system symbols are platform/development dependencies; proprietary Apple SDK/framework binaries are not redistributed here.

## Artwork and standards

The public source repository contains no custom app artwork. The downloadable app includes a project-selected custom icon; its source document and provenance are not distributed in this repository. DICOM attribute names/numeric tags are used by the implementation, but no complete standards table or conformance archive is redistributed. DICOM is a standards name, not a project endorsement. Contributor submissions must preserve any applicable notices and document third-party origins.
