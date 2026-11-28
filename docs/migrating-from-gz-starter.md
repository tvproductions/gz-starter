# Move an adopter from GZ Starter to gzlite 0.14.0

Use the published [gzlite 0.14.0 release](https://github.com/tvproductions/gzlite/releases/tag/v0.14.0).
Read the release notes, confirm the exact commit behind the annotated tag,
and use its full SHA for every command. Run from the adopter root, with a clean
Git worktree and the adopter's own instructions in scope.

For an assistant handling the migration, use this instruction.

> Use the published gzlite 0.14.0 commit and the adopter's project instructions.
> Show me the migration preview and its fingerprint. Apply that preview only
> when I name its fingerprint. Then show the freshen preview for separate
> approval. Check the resulting lock, project diff, status and verifier output.

## Verify the release and preview the move

```console
gh release view v0.14.0 --repo tvproductions/gzlite --json tagName,targetCommitish
git ls-remote --tags https://github.com/tvproductions/gzlite.git "refs/tags/v0.14.0*"
```

Use the peeled commit shown on the `refs/tags/v0.14.0^{}` line. Confirm it equals
the full release target. Replace `FULL_RELEASE_SHA` in the following commands.
uv runs the named release using managed Python 3.14. Keep the same release SHA
throughout the operation.

```console
uvx --managed-python --python 3.14 --from "gzlite @ git+https://github.com/tvproductions/gzlite.git@FULL_RELEASE_SHA" gzlite migrate --project . --starter-ref FULL_RELEASE_SHA
```

Review the planned writes, preserved files and findings. If the maintainer
accepts the preview, repeat the same command with
`--apply --fingerprint REVIEWED_MIGRATE_FINGERPRINT`. Stop and review again
if the fingerprint changes. Keep the migration's saved copies until the
tracked project diff has been reviewed.

## Preview the release reconciliation

```console
uvx --managed-python --python 3.14 --from "gzlite @ git+https://github.com/tvproductions/gzlite.git@FULL_RELEASE_SHA" gzlite freshen --project . --starter-ref FULL_RELEASE_SHA
```

Review this preview independently. Apply with
`--apply --fingerprint REVIEWED_FRESHEN_FINGERPRINT` only if the maintainer
accepts this fingerprint. Review the new `.gzlite/bundle.lock.json` and the
project diff. Run `gzlite status --project .` using the same pinned command
prefix. For adopters already using the verification extra, reconcile the
project's verifier dependency and lock as shown in the findings, then run
`uv run --locked gzlite verify --project .`.

uv commonly stores the verifier requirement as `gz-starter[verification]`
in the development group plus a `gz-starter` entry in `[tool.uv.sources]`.
If that form remains after migration, change the requirement to
`gzlite[verification]`, rename the source key to `gzlite`, and set its
`git` URL to `https://github.com/tvproductions/gzlite.git` and its `rev`
to the verified full release SHA. Keep existing markers and unrelated group
entries. Run `uv lock`, inspect the diff, then run the locked verifier.

The preview can report older untagged GZ Starter revisions supported by the
embedded migration history. The new target must be tagged. Verify native
skill discovery in a fresh session for every host used by the project.
The project-scoped update skill is now `gzl-update`.

