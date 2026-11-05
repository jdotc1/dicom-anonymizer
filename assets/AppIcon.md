# App icon

`AppIcon.icon` is an Icon Composer document in the Lumen family: a violet
accent, flat vector layers, and the system's Liquid Glass for depth. Light and dark appearances are
defined in the document.

The mark is the app's job in one picture: a glass patient tag in front of an MRI slice in a steel bezel.
The left half of the tag is the identity, shown as silver text lines. The right half is the pseudonym,
shown as a 2x2 grid of violet tiles. A glowing divider joins them, and the slice behind stays intact. The
slice is a synthetic, procedurally drawn axial pelvis image; it contains no patient pixels.

`build.sh` compiles it with `actool` into `Assets.car` (macOS 26 and later) and `AppIcon.icns`
(earlier systems). Edit it in Icon Composer. The document uses three groups, because Icon Composer
allows at most four.
