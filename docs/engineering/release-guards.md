# Release safeguards

Use `gzlite release check` from a full publisher checkout with all version tags.
The offline check compares bundle metadata, both marketplace names and the dated
changelog with the annotated tags and their commits. From 0.14.0 forward, the
tagged commit first sets the version mirrors and dates the changelog entry.
Run `gzlite release check --published` after publication to verify the GitHub
release records and their exact tagged revisions. Pull request CI makes a
local annotated tag for the proposed release commit when that tag has yet
to be created on the publisher. Main and local checks require the actual tag.

The [GitHub ruleset definitions](../../tools/github_rules.json) require a PR and
the `gate` and `release-integrity` checks on `main`, block force pushes and
deletion of `main`, and block moving or deleting version tags. A separate rule
restricts version tag creation. Its bypass actor must be the explicitly approved
maintainer team. Keeping the rules separate preserves the immutability rule for
that team.

## Apply the GitHub settings

Obtain the maintainer's explicit approval of the live settings and the team
before applying. Verify that `tvproductions/gzlite` is repository ID
`1411853335` and inventory existing rulesets. Compare by name and update matching
entries with `PUT` at their numeric ID. Create absent rulesets with `POST`.

```bash
repo=tvproductions/gzlite
gh repo view "$repo" --json nameWithOwner,defaultBranchRef
gh api "repos/$repo" --jq .id
gh api "repos/$repo/rulesets"
team_id="$(gh api "orgs/tvproductions/teams/<approved-team-slug>" --jq .id)"
jq '.main' tools/github_rules.json |
  gh api --method POST "repos/$repo/rulesets" --input -
jq '.tags' tools/github_rules.json |
  gh api --method POST "repos/$repo/rulesets" --input -
jq --argjson team_id "$team_id" \
  '.publishers | .bypass_actors = [{"actor_type":"Team","actor_id":$team_id,"bypass_mode":"always"}]' \
  tools/github_rules.json |
  gh api --method POST "repos/$repo/rulesets" --input -
gh api --method PUT "repos/$repo/immutable-releases"
gh api "repos/$repo/immutable-releases"
gh api "repos/$repo/rules/branches/main"
gh api "repos/$repo/rulesets"
```

Inspect each rule's exact payload and bypass actors using
`gh api "repos/$repo/rulesets/<id>"`. Verify both the tag and GitHub release
against the intended commit. Preserve old releases and tag objects.

References. [Ruleset endpoints](https://docs.github.com/en/rest/repos/rules)
and [immutable release settings](https://docs.github.com/en/rest/repos/repos#enable-immutable-releases).

