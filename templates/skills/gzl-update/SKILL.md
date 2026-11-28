---
name: gzl-update
description: Review or migrate a project's adopted GZ Lite template using the pinned gzlite release and fingerprint-reviewed previews. Use for template updates and version reviews.
---

# Update GZ Lite

Work from the adopter root and follow its instructions. Resolve the selected
release at `tvproductions/gzlite`. Confirm that its annotated tag peels to the
full SHA advertised by the release. Use the same SHA for the command package
and the target of each preview. The
[adopter bridge](https://github.com/tvproductions/gzlite/blob/main/docs/migrating-from-gz-starter.md)
shows how to check the tag and run the pinned CLI through uv.

1. If the adopter has legacy state, preview
   `gzlite migrate --project . --starter-ref FULL_RELEASE_SHA` using the
   pinned CLI. Show the planned changes and findings. On approval, apply
   only the named migration fingerprint. Finish the migration before
   running freshen.
2. Preview `gzlite freshen --project . --starter-ref FULL_RELEASE_SHA`.
   Show the planned changes and findings. On approval, apply only the
   named freshen fingerprint.
3. After applying, run `gzlite status --project .` with the pinned CLI and
   `uv run --locked gzlite verify --project .` if the adopter uses the
   verification extra. Review the project diff and report the outcomes.

A version or freshness review authorizes previews only. Stop on a changed
fingerprint and review the new plan before applying.
