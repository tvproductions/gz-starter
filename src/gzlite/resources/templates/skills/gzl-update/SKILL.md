---
name: gzl-update
description: Update a project's adopted GZ Lite template with the gzlite commands, reviewing each preview with the maintainer. Use for GZ Lite version reviews and template upgrades, rather than general package or plugin updates.
---

# Update GZ Lite

GZ Lite (`gzlite`, repository `tvproductions/gzlite`) is highly opinionated: my
way or the highway. Adopters conform to its doctrine; do not bend the template
to local habit. The commands enforce the rules, so run them and show what they
report instead of reasoning around them.

1. If `.gz-starter/` or `.skills-first/` exists, run
   `gzlite migrate --project .` and show the preview and its findings.
2. Run `gzlite freshen --project .`. Show the maintainer each preview and its
   findings, unedited.
3. Apply only the fingerprint the maintainer names:
   `gzlite freshen --project . --apply --fingerprint <hash>`. Never choose or
   infer a fingerprint, and never apply without one.
4. Run `gzlite status`, and `gzlite verify` where the project uses it. Report
   the results as observed.
5. Work the remaining findings with Superpowers, one bounded change at a time.

`migrate` and `freshen` are the supported commands of this release. A review
request authorizes steps 1 and 2 only.
