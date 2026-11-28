"""Build the embedded starter release history from the starter's commits.

Run from a full clone that has the tags ``v0.1.0`` to ``v0.14.0``:

    uv run --locked python tools/build_release_history.py [--check]

Adopters record untagged revisions as well as tagged ones, and untagged commits
often wrote different templates (and declared versions such as 0.3.2 that were
never tagged). So for every commit reachable from ``v0.13.0`` that has a release
tag among its ancestors, the builder reads that commit's own ``configure`` code
with ``git cat-file`` and derives, by static analysis (never by running historical
code), what ``configure`` wrote: the declared version, the managed paths per host,
their conditions, the lock keys, and the templates as raw text with placeholders.
Identical results are stored once, as a snapshot keyed by version and content
hash. It refuses to guess: any construct it does not recognize stops the build.
From gzlite v0.14.0 onward, configure requires an exact published tag, so only
the tagged release commits need snapshots for freshen.
The gate never runs this tool; it reads only the committed
``src/gzlite/resources/release_history.json``.

Every git call strips inherited ``GIT_*`` variables and names the repository
explicitly, so running under a hook never redirects git to another repository.
The builder only reads history; it never runs a git command that writes.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

from gzlite.gitenv import clean_git_env
from gzlite.release_check import released_versions

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = Path("src/gzlite/resources/release_history.json")
SCHEMA_VERSION = 1
LAST_STARTER_TAG = "v0.13.0"
LAST_HISTORY_TAG = "v0.14.0"
TAG = re.compile(r"v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\Z")
PACKAGE = "src/skills_first_starter"
FRAGMENT_SOURCE = "templates/AGENTS.skills-first.md"
PLACEHOLDERS = ("{{ADR_POLICY_WORKING_SOURCE}}", "{{ADR_POLICY_CANONICAL_URL}}")
REPOSITORY_URL = "https://github.com/tvproductions/"
# Sentinels for candidate keys that depend on the selected host.
HOST_CONFIG = "<host configuration>"
UPDATE_SKILL_KEY = "<update skill>"


class BuildError(Exception):
    """A tag's code does not match a shape the builder can read with confidence."""


def git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Run a read-only git command against ``repo`` only."""
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        cwd=repo,
        env=clean_git_env(),
        check=check,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def git_blob(repo: Path, commit: str, path: str) -> bytes:
    """Read one file's exact bytes at ``commit``; templates must not be re-encoded."""
    return subprocess.run(
        ["git", "-C", str(repo), "cat-file", "blob", f"{commit}:{path}"],
        cwd=repo,
        env=clean_git_env(),
        check=True,
        capture_output=True,
    ).stdout


def version_key(tag: str) -> tuple[int, ...]:
    match = TAG.fullmatch(tag)
    if match is None:
        raise BuildError(f"not a release tag: {tag}")
    return tuple(int(part) for part in match.groups())


def history_tags(repo: Path) -> list[str]:
    """Return the published tags included in this history build, in version order."""
    names = git(repo, "tag", "--list", "v*").stdout.split()
    limit = version_key(LAST_HISTORY_TAG)
    tags = sorted(
        (name for name in names if TAG.fullmatch(name) and version_key(name) <= limit),
        key=version_key,
    )
    for required in (LAST_STARTER_TAG, LAST_HISTORY_TAG):
        if required not in tags:
            raise BuildError(f"{required} is missing; build from a full clone with tags")
    return tags


def commit_of(repo: Path, ref: str) -> str:
    return git(repo, "rev-parse", "--verify", f"{ref}^{{commit}}").stdout.strip()


def revision_map(repo: Path, tags: list[str], head: str) -> dict[str, str]:
    """Map every commit reachable from ``head`` to its latest ancestor-or-equal tag.

    Commits with no tag among their ancestors are left out, so they stay unknown.
    """
    mapping: dict[str, str] = {}
    ordered = sorted(tags, key=version_key)
    # Version order must be ancestry order, or "latest tag" would be ambiguous.
    for earlier, later in zip(ordered, [*ordered[1:], head], strict=True):
        if git(repo, "merge-base", "--is-ancestor", earlier, later, check=False).returncode != 0:
            raise BuildError(f"{earlier} is not an ancestor of {later}")
    for tag in ordered:
        mapping[commit_of(repo, tag)] = tag
        # Descendants of the tag that are ancestors of head; a later tag overwrites.
        for line in git(repo, "rev-list", "--ancestry-path", f"{tag}..{head}").stdout.split():
            mapping[line] = tag
    return mapping


def static(node: ast.expr, env: dict[str, str]) -> str:
    """Evaluate a string expression built only from literals and known names."""
    match node:
        case ast.Constant(value=str() as value):
            return value
        case ast.Name(id=name) if name in env:
            return env[name]
        case ast.JoinedStr(values=values):
            return "".join(static(value, env) for value in values)
        case ast.FormattedValue(value=value, conversion=-1, format_spec=None):
            return static(value, env)
        case ast.IfExp(test=ast.Compare(left=left, ops=[ast.Eq()], comparators=[right])):
            chosen = node.body if static(left, env) == static(right, env) else node.orelse
            return static(chosen, env)
        case ast.Call(
            func=ast.Attribute(value=value, attr="removesuffix"), args=[suffix], keywords=[]
        ):
            return static(value, env).removesuffix(static(suffix, env))
    raise BuildError(f"cannot evaluate statically: {ast.unparse(node)}")


def constants(tree: ast.Module, env: dict[str, str]) -> dict[str, str]:
    """Collect module-level string constants, resolving earlier names."""
    found = dict(env)
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name):
                try:
                    found[target.id] = static(node.value, found)
                except BuildError:
                    continue
    return found


def function(tree: ast.Module, name: str) -> ast.FunctionDef:
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise BuildError(f"function {name} not found")


def call_static(tree: ast.Module, name: str, env: dict[str, str]) -> str:
    """Evaluate a function made only of string assignments and one return."""
    local = dict(env)
    for statement in function(tree, name).body:
        match statement:
            case ast.Expr(value=ast.Constant(value=str())):
                continue
            case ast.Assign(targets=[ast.Name(id=target)], value=value):
                local[target] = static(value, local)
            case ast.Return(value=ast.expr() as value):
                return static(value, local)
            case _:
                raise BuildError(f"{name} has an unsupported statement")
    raise BuildError(f"{name} does not return")


def assigned(tree: ast.Module, name: str, kind: type[ast.expr]) -> list[ast.expr]:
    """Return every value of ``kind`` assigned to the plain name ``name``."""
    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id == name
        and isinstance(node.value, kind)
    ]


def only(values: list, what: str):
    if len(values) != 1:
        raise BuildError(f"expected exactly one {what}, found {len(values)}")
    return values[0]


def subscript_assigns(tree: ast.Module, name: str) -> list[ast.Assign]:
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Subscript)
        and isinstance(node.targets[0].value, ast.Name)
        and node.targets[0].value.id == name
    ]


def strings(tree: ast.Module) -> set[str]:
    return {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }


def here_sources(node: ast.AST, env: dict[str, str]) -> list[str]:
    """Return the starter-relative files read as ``HERE / <path>`` inside ``node``."""
    return [
        static(item.right, env)
        for item in ast.walk(node)
        if isinstance(item, ast.BinOp)
        and isinstance(item.op, ast.Div)
        and isinstance(item.left, ast.Name)
        and item.left.id == "HERE"
    ]


def as_read_text(data: bytes) -> str:
    """Decode as ``Path.read_text`` did: UTF-8 with universal newlines."""
    return data.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")


class Tree:
    """The files of one starter commit, read through git."""

    def __init__(self, repo: Path, commit: str) -> None:
        self.repo = repo
        self.commit = commit
        self.files = set(git(repo, "ls-tree", "-r", "--name-only", commit).stdout.splitlines())
        self.package = "src/gzlite" if "src/gzlite/cli.py" in self.files else PACKAGE

    def read(self, path: str) -> bytes:
        if path not in self.files:
            raise BuildError(f"{self.commit} has no {path}")
        return git_blob(self.repo, self.commit, path)

    def source(self, path: str) -> bytes:
        """Read a template; wheels carried a mirror that must match the checkout file."""
        data = self.read(path)
        mirror = f"{self.package}/resources/{path}"
        if mirror in self.files and git_blob(self.repo, self.commit, mirror) != data:
            raise BuildError(f"{self.commit} wheel resource {mirror} differs from {path}")
        return data

    def module(self, path: str) -> ast.Module | None:
        return (
            ast.parse(self.read(path), filename=f"{self.commit}:{path}")
            if path in self.files
            else None
        )


def candidate_key(node: ast.expr | None, env: dict[str, str]) -> str:
    match node:
        case ast.Name(id="config_path"):
            return HOST_CONFIG
        case ast.Call(func=ast.Name(id="update_skill_path")):
            return UPDATE_SKILL_KEY
        case ast.expr():
            return static(node, env)
    raise BuildError("configure candidates use dictionary unpacking")


def is_absent_check(test: ast.expr) -> bool:
    """Match ``not <path>.exists()``."""
    match test:
        case ast.UnaryOp(op=ast.Not(), operand=ast.Call(func=ast.Attribute(attr="exists"))):
            return True
    return False


def conditional_candidates(cli: ast.Module, env: dict[str, str]) -> dict[str, str]:
    """Return ``candidates[path] = <text>`` writes guarded by an absence check."""
    found = {}
    for node in ast.walk(cli):
        if isinstance(node, ast.If) and is_absent_check(node.test):
            for statement in node.body:
                if statement in subscript_assigns(cli, "candidates"):
                    assert isinstance(statement, ast.Assign)
                    target = statement.targets[0]
                    assert isinstance(target, ast.Subscript)
                    found[static(target.slice, env)] = static(statement.value, env)
    if len(found) != len(subscript_assigns(cli, "candidates")):
        raise BuildError("a configure candidate is added outside an absence check")
    return found


def adr_local_copies(cli: ast.Module, env: dict[str, str]) -> list[str]:
    """Return paths that ``candidates.update(copies)`` adds in ADR local mode."""
    updates = [
        node
        for node in ast.walk(cli)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "update"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "candidates"
    ]
    if not updates:
        return []
    update = only(updates, "candidates.update call")
    match update.args:
        case [ast.Name(id="copies")]:
            pass
        case _:
            raise BuildError("candidates.update does not add the ADR policy copies")
    copies = only(assigned(cli, "copies", ast.IfExp), "ADR policy copies expression")
    match copies:
        case ast.IfExp(
            test=ast.Compare(
                left=ast.Name(id="mode"), ops=[ast.Eq()], comparators=[ast.Constant("local")]
            ),
            body=ast.Dict(keys=[key]),
            orelse=ast.Dict(keys=[]),
        ) if key is not None:
            return [static(key, env)]
    raise BuildError("ADR policy copies are not conditional on local mode")


def lock_keys(cli: ast.Module, env: dict[str, str]) -> list[str]:
    lock = only(assigned(cli, "lock", ast.Dict), "lock literal")
    assert isinstance(lock, ast.Dict)
    keys = [static(key, env) for key in lock.keys if key is not None]
    for node in subscript_assigns(cli, "lock"):
        target = node.targets[0]
        assert isinstance(target, ast.Subscript)
        keys.append(static(target.slice, env))
    return keys


def adr_policy_url(cli: ast.Module, env: dict[str, str]) -> str | None:
    """Return the canonical policy URL with ``{ref}`` left for the adopter's revision."""
    urls = {
        static(value, {**env, "ref": "{ref}"})
        for name in ("policy_url", "url")
        for value in assigned(cli, name, ast.JoinedStr)
    }
    return only(sorted(urls), "ADR policy URL") if urls else None


def marketplace(tree: Tree, env: dict[str, str], version: str) -> str:
    names = {
        json.loads(tree.read(path))["name"]
        for path in (".agents/plugins/marketplace.json", ".claude-plugin/marketplace.json")
    }
    name = only(sorted(names), "catalog name shared by both native catalogs")
    if "MARKETPLACE" in env and env["MARKETPLACE"] != name:
        raise BuildError(f"{tree.commit} MARKETPLACE constant differs from its catalogs")
    prefix = "gzlite-" if tree.package == "src/gzlite" else "gz-starter-"
    if "MARKETPLACE" not in env and name != prefix + version.replace(".", "-"):
        raise BuildError(f"{tree.commit} catalog name does not follow the versioned rule")
    return name


def host_paths(native: ast.Module | None, env: dict[str, str]) -> dict[str, str]:
    if native is None:
        return {"codex": ".codex/config.toml"}
    table = only(assigned(native, "HOST_PATHS", ast.Dict), "HOST_PATHS table")
    assert isinstance(table, ast.Dict)
    return {
        static(k, env): static(v, env) for k, v in zip(table.keys, table.values, strict=True) if k
    }


def jsonc_alternative(native: ast.Module | None) -> bool:
    """OpenCode ``opencode.jsonc`` is repaired in place when it already exists."""
    if native is None:
        return False
    return "opencode.jsonc" in strings(ast.Module(body=[function(native, "configuration_path")]))


def expand(
    key: str, host: str, hosts: dict[str, str], native: ast.Module | None, env: dict[str, str]
) -> list[str]:
    if key == HOST_CONFIG:
        entries = ["merged:" + hosts[host]]
        if host == "opencode" and jsonc_alternative(native):
            entries.append("merged-if-exists:opencode.jsonc")
        return entries
    if key == UPDATE_SKILL_KEY:
        if native is None:
            raise BuildError("update_skill_path is used without native.py")
        return [call_static(native, "update_skill_path", {**env, "host": host})]
    if key in hosts.values():
        return ["merged:" + key]
    return [key]


def snapshot(repo: Path, commit: str) -> dict:
    """Derive what ``configure`` at commit ``commit`` wrote, from its code alone."""
    tree = Tree(repo, commit)
    packaged = f"{tree.package}/cli.py" in tree.files
    cli = tree.module(f"{tree.package}/cli.py" if packaged else "starter.py")
    native = tree.module(f"{tree.package}/native.py") if packaged else None
    paths = tree.module(f"{tree.package}/paths.py") if packaged else None
    assert cli is not None
    env = constants(cli, constants(paths, {}) if paths else {})
    version = json.loads(tree.read("bundle.json"))["template_version"]
    origin = env["ORIGIN"]
    if native is not None:
        urls = {text for text in strings(native) if text.startswith(REPOSITORY_URL)}
        if urls - {origin}:
            raise BuildError(f"{commit} native.py names another starter origin: {urls}")

    gzlite = tree.package == "src/gzlite"
    configuration = ast.Module(body=[function(cli, "_configuration_candidates")]) if gzlite else cli
    table = only(assigned(configuration, "candidates", ast.Dict), "configure candidates literal")
    assert isinstance(table, ast.Dict)
    keys = [candidate_key(key, env) for key in table.keys]
    hosts = host_paths(native, env)
    if native is None and ".codex/config.toml" not in keys:
        raise BuildError(f"{commit} configure does not write the Codex configuration")
    absent = conditional_candidates(configuration, env)
    local = adr_local_copies(cli, env)
    if FRAGMENT_SOURCE not in here_sources(cli, env) or "AGENTS.skills-first.md" not in keys:
        raise BuildError(f"{commit} does not write the fragment from {FRAGMENT_SOURCE}")

    update_skill = env.get("UPDATE_SKILL")
    update_template = None
    if update_skill is not None:
        update_template = as_read_text(tree.source(env["UPDATE_SKILL_SOURCE"]))
    front_door = front_template = None
    for key, value in zip(keys, table.values, strict=True):
        skill = key.removeprefix(".agents/skills/").removesuffix("/SKILL.md")
        if key.startswith(".agents/skills/") and "/" not in skill and skill != update_skill:
            if front_door is not None:
                raise BuildError(f"{commit} writes more than one starter skill")
            front_door = skill
            front_template = as_read_text(
                tree.source(only(here_sources(value, env), "skill source"))
            )

    managed = {}
    for host in sorted(hosts):
        entries = [entry for key in keys for entry in expand(key, host, hosts, native, env)]
        entries += ["if-absent:" + path for path in absent]
        entries += ["adr-local:" + path for path in local]
        if update_skill is not None and not any(
            entry.endswith(f"/skills/{update_skill}/SKILL.md") for entry in entries
        ):
            raise BuildError(f"{commit} does not write {update_skill} for {host}")
        managed[host] = entries
    locks = [entry for entry in managed[sorted(hosts)[0]] if entry.endswith("/bundle.lock.json")]
    state_directory = only(locks, "bundle lock path").rpartition("/")[0]

    fragment = as_read_text(tree.source(FRAGMENT_SOURCE))
    placeholders = all(text in strings(cli) for text in PLACEHOLDERS)
    if placeholders != all(text in fragment for text in PLACEHOLDERS):
        raise BuildError(f"{commit} fragment placeholders and configure rendering disagree")
    adr_source = env.get("ADR_POLICY_SOURCE")
    if (adr_source is None) != (not local):
        raise BuildError(f"{commit} ADR policy source and local copy disagree")
    return {
        "version": version,
        "origin": origin,
        "state_directory": state_directory,
        "marketplace": marketplace(tree, env, version),
        "fragment_template": fragment,
        "update_skill": update_skill,
        "update_skill_template": update_template,
        "adr_placeholders": placeholders,
        "hosts": sorted(hosts),
        "managed_paths": managed,
        "front_door_skill": front_door,
        "front_door_skill_template": front_template,
        "agents_md_template": only(list(absent.values()), "default AGENTS.md text"),
        "lock_keys": lock_keys(configuration, env),
        "adr_policy_source": adr_source,
        # configure copied the policy with read_bytes, so its newlines are kept as-is.
        "adr_policy_template": tree.source(adr_source).decode("utf-8") if adr_source else None,
        "adr_policy_url": (
            call_static(cli, "_adr_policy_url", {**env, "ref": "{ref}"})
            if gzlite
            else adr_policy_url(cli, env)
        ),
    }


def snapshot_id(data: dict) -> str:
    """Name a snapshot by its declared version and a hash of its canonical JSON."""
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"{data['version']}-{hashlib.sha256(canonical).hexdigest()[:12]}"


def refuse_release_gaps(repo: Path) -> None:
    """Find the commit that first dated any release with no corresponding tag."""
    tags = set(git(repo, "tag", "--list", "v*").stdout.splitlines())
    commits = git(repo, "log", "--reverse", "--first-parent", "--format=%H", "--", "CHANGELOG.md")
    for commit in commits.stdout.splitlines():
        changelog = git(repo, "show", f"{commit}:CHANGELOG.md", check=False).stdout
        missing = sorted(
            version for version in released_versions(changelog) if f"v{version}" not in tags
        )
        if missing:
            raise BuildError(f"dated release {missing[0]} at {commit} has no tag")


def build(repo: Path) -> str:
    refuse_release_gaps(repo)
    tags = history_tags(repo)
    starter_tags = tags[: tags.index(LAST_STARTER_TAG) + 1]
    gzlite_tags = tags[len(starter_tags) :]
    nearest = revision_map(repo, starter_tags, LAST_STARTER_TAG)
    nearest.update({commit_of(repo, tag): tag for tag in gzlite_tags})
    snapshots: dict[str, dict] = {}
    revisions = {}
    for commit in sorted(nearest):
        data = snapshot(repo, commit)
        ident = snapshot_id(data)
        if snapshots.setdefault(ident, data) != data:
            raise BuildError(f"snapshot id collision at {commit}")
        revisions[commit] = {"snapshot": ident, "tag": nearest[commit]}
    releases = []
    for tag in tags:
        commit = commit_of(repo, tag)
        entry = revisions[commit]
        version = snapshots[entry["snapshot"]]["version"]
        if entry["tag"] != tag or version != tag.removeprefix("v"):
            raise BuildError(f"{tag} bundle.json records template_version {version}")
        releases.append({"tag": tag, "revision": commit, "snapshot": entry["snapshot"]})
    total = int(git(repo, "rev-list", "--count", LAST_STARTER_TAG).stdout) + len(gzlite_tags)
    print(
        f"{len(tags)} releases; {len(revisions)} of {total} commits mapped to "
        f"{len(snapshots)} snapshots; {total - len(revisions)} predate {tags[0]}",
        file=sys.stderr,
    )
    data = {
        "schema_version": SCHEMA_VERSION,
        "snapshots": snapshots,
        "releases": releases,
        "revisions": revisions,
    }
    return json.dumps(data, indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", type=Path, default=ROOT, help="full clone with release tags")
    parser.add_argument("--check", action="store_true", help="report drift without writing")
    args = parser.parse_args()
    repo = args.repo.resolve()
    try:
        text = build(repo)
    except (BuildError, subprocess.CalledProcessError, KeyError, ValueError) as error:
        parser.exit(2, f"release history build blocked: {error}\n")
    target = ROOT / OUTPUT
    encoded = text.encode("utf-8")
    if args.check:
        if not target.is_file() or target.read_bytes() != encoded:
            parser.exit(1, f"Stale release history: {OUTPUT.as_posix()}\n")
        return 0
    target.write_bytes(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
