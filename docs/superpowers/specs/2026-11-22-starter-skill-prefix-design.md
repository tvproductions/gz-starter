# Starter-owned skill prefix

On November 22, 2026, the maintainer replied “ok, approved” to the proposal to
rename `update-gz-template` to `gzt-update-template` in the next minor release.
Use `gzt-` for every skill GZ Starter authors and ships. The approved
proposal covers the existing skill and preserves the selected 0.12.1 scope.

## Approach

Ship a single canonical `gzt-update-template` skill. The authored directory,
frontmatter, checkout discovery link, packaged resource, and host-specific
output directories agree on that ID. Apply the existing skill ownership and
exact-source verification decisions. The CLI remains `gz-starter`, and bundled
plugins and project-owned skills use their owners' names.

A permanent discovery alias would expose two names for the same workflow.
An unconditional replacement would risk losing adopter edits. Use the existing
reviewed template-update procedure for the rename. Compare the released legacy
skill, the adopter's copy, and the candidate. Reconcile local edits and live
references, retain the original in Git history, and retire the old discovery
path as part of the reviewed change. Keep the documentation entry available to
older adopters and preserve their recorded provenance until the upgrade applies.

New adoptions get one canonical copy on their selected host. Configure detects
a legacy skill on any scanned discovery surface and reports reconciliation
before writing. Dual-name or alternate-surface copies also require review.
Adoption configuration and activation repair remain separate. A verifier-only
update retains support for the exact legacy checkout link to its matching
authored directory, without installing or activating another copy. Both link
names remain bounded to their exact corresponding targets.

Prove clean adoption, preservation on refusal, the reviewed migration and
rollback, packaged installation, and fresh native discovery. The pending
0.12.1 state-directory patch retains its approved scope. The next minor target
is 0.13.0 after the patch. This design authorizes neither new skills nor
publication or changes to real adopters.
