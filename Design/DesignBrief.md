# Workflow polish brief — 2026-10-14

Personality: calm, precise, restrained, legible, dependable.

Primary workflow: choose the parent batch folder, inspect numerical patient identifiers, choose output, anonymize, then reveal the completed batch or report. Preserve the engine policy and read-only input workflow.

Window anatomy: one column containing batch input, patient preview, output, policy, activity/result and primary actions. Private uses Lumen foundation components; public keeps native SwiftUI and has no Lumen dependency.

Typography: preserve each variant's existing Arial sizing and monospaced identifiers; use weight and spacing for hierarchy. Do not shrink controls or text to fit long paths.

Spacing/radii/materials: retain existing variant metrics and semantic window/control surfaces. No new decorative glass, panels or navigation layer.

Accent: retain the existing app accent and semantic status colors. SF Symbols stay limited to existing folder, image-series, progress and completion roles. Preserve the approved Icon Composer artwork/resources without regeneration.

Components: input, patient rows, output property, progress, completion summary and native File commands. Full paths remain available through help; long visible labels truncate in the middle. Completion actions have a separate row.

States: empty, populated, preparing, processing, finalizing, error and complete. Writing 100% is not completion: use an indeterminate finalizing state until the existing complete event arrives. An error disables processing, including the keyboard command.

Accessibility: retain VoiceOver labels, textual status, numerical IDs, keyboard navigation and light/dark parity. Add discoverable output/recheck/reveal/report shortcuts and helpful disabled-action explanations.

Verification: compile changed real targets once; exercise presentation states with synthetic model state and check the public error guard. Reuse unchanged engine, self-audit, runtime, icon, theme and notarization receipts. Do not process another batch, replace the installed app or publish a release for this pass.
