# Release automation delivery — 2026-10-23

The receipt-driven workflow assembled public Preview 11/app build 15 from accepted app-source `35c967c`, with release-tooling merge `546640d`. Apple accepted notarization `6d2d57f0-5b5b-48d7-91a2-2a9f345de687`. The new root signature, stapled ticket and Gatekeeper assessment passed once. Accepted executable, engine, policy, UI, Python, icon and nested-signature evidence was reused; no unchanged suite, build, provenance hash or dependency check was repeated. The existing interface and engine policy are unchanged. The standalone arm64 ZIP was published and its HTTPS delivery returned HTTP 200. This is macOS 13+ and requires no external Python installation.

See [Release automation](RELEASE-AUTOMATION.md) for the recipe and resumable stages, and [tooling evidence](RELEASE-AUTOMATION-EVIDENCE.md) for focused fixture/source-review coverage. New distribution acceptance does not expand the earlier runtime or clinical acceptance scope.
