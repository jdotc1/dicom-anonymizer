# Release automation implementation evidence

This source-only increment adds receipt-driven assembly and explicit resumable
signing, notarization, and final archive steps. It does not change application
interfaces or engine policy. At that source-only checkpoint it had not been used to produce a real release.

Sixteen assembly fixture cases and ten shared distribution-stage cases supplied focused evidence. Successful unchanged cases were reused; only changed fixtures and affected paths were checked again.

Coverage includes accepted Git engine selection instead of working-tree contents,
resource and nested-signature preservation, variant/metadata/build guards, unsafe
symlink rejection, rollback, root-only signing arguments, cached stages, locking,
and interrupted notarization reconciliation. Distribution commands were mocked;
this is tooling evidence, not real signing/notarization/runtime acceptance.

The accepted storage-recovery and delivered Preview 10 records remain the
application evidence for their original inputs. No unchanged app, engine, policy,
self-audit, runtime, icon, UI, dependency, or signing verification was repeated.
No real build, sign, notarize, publish, or install operation ran for this increment.
Local tooling logs and the detailed tooling-receipt.json are retained in the
release-automation workspace. App release versions remain unchanged.

## Subsequent authorized distribution

The receipt-driven workflow assembled public Preview 11/app build 15 from accepted app-source `35c967c`, with release-tooling merge `546640d`. Apple accepted notarization `6d2d57f0-5b5b-48d7-91a2-2a9f345de687`. The new root signature, stapled ticket and Gatekeeper assessment passed once. Accepted executable, engine, policy, UI, Python, icon and nested-signature evidence was reused; no unchanged suite, build, provenance hash or dependency check was repeated. The existing interface and engine policy are unchanged. The standalone arm64 ZIP was published and its HTTPS delivery returned HTTP 200. This is macOS 13+ and requires no external Python installation.
