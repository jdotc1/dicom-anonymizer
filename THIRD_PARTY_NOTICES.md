# Third-party notices

The project source license is in LICENSE. That license does not replace dependency licenses or grant rights to third-party trademarks.

## pydicom

The Python engine depends on pydicom 3.0.2. The source-only repository distributes a dependency requirement rather than a vendored copy. The optional local app build copies the installed pydicom package and its complete distribution metadata/license into the app's vendor resources. Preserve those notices whenever redistributing that package.

The upstream license is MIT-based with component-specific exceptions. Review the actual installed version's complete LICENSE and bundled notices; do not replace them with only this summary. Upstream: https://github.com/pydicom/pydicom and https://github.com/pydicom/pydicom/blob/main/LICENSE.

## Python and Apple development tools

Python is an external runtime and is not bundled. A future bundled runtime requires its own redistribution and license review. Xcode, SwiftUI, AppKit, Foundation and system symbols are platform/development dependencies; their proprietary SDK/framework binaries are not redistributed here.

## Artwork and standards

No third-party or recovered custom app artwork is included. DICOM attribute names/numeric tags are used by the implementation, but no complete standards table or private conformance archive is redistributed. DICOM is a standards name, not a project endorsement. Contributor submissions must preserve any applicable notices and document third-party origins.
