# Application design

Personality: calm, precise, restrained, legible, dependable.

Primary workflow: choose the parent batch folder, inspect numerical patient identifiers, choose output, anonymize, then reveal the completed batch or report. Preserve the engine policy and read-only input workflow.

Window anatomy: one native SwiftUI column containing batch input, patient preview, output, policy, activity/result and primary actions.

Typography: preserve existing native text sizes and monospaced identifiers; use weight and spacing for hierarchy. Do not shrink controls or text to fit long paths.

Spacing/radii/materials: retain existing metrics and semantic window/control surfaces. No decorative glass, panels or additional navigation layer.

Accent: retain the existing app accent and semantic status colors. SF Symbols stay limited to existing folder, image-series, progress and completion roles. Preserve the distributed app icon resources.

Components: input, patient rows, output property, progress, completion summary and native File commands. Full paths remain available through help; long visible labels truncate in the middle. Completion actions have a separate row.

States: empty, populated, preparing, processing, finalizing, error and complete. Writing 100% is not completion: use an indeterminate finalizing state until the existing complete event arrives. An error disables processing, including the keyboard command.

Accessibility: preserve existing VoiceOver labels, textual status, numerical IDs, keyboard navigation, shortcuts, disabled-action explanations and light/dark behavior.

Verification: match checks to the changed behavior, distinguish synthetic model coverage from live interaction evidence, and reuse accepted verification for unchanged inputs.
