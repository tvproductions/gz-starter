"""Verify built artifacts and installed CLI behavior outside the checkout."""

import hashlib
import json
import os
import secrets
import subprocess
import sys
import tarfile
import tempfile
import tomllib
import zipfile
from email.parser import BytesParser
from pathlib import Path

from gzlite.cli import ORIGIN
from gzlite.gitenv import clean_git_env

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = "gzlite/resources/templates/verification/verify-python.yml"


def run(
    *command: str, cwd: Path, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    """Run a verification command and retain decoded failure diagnostics."""
    return subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        encoding="utf-8",
        errors="strict",
        capture_output=True,
        check=True,
    )


def verify_archives(wheel: Path, sdist: Path) -> None:
    """Allow only the owned update skill and verify every packaged resource."""
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        if WORKFLOW not in names:
            raise ValueError("Wheel is missing the supported adopter workflow")
        verify_extra_metadata(archive)
        skill = "templates/skills/gzl-update/SKILL.md"
        allowed = f"gzlite/resources/{skill}"
        if {name for name in names if name.endswith("/SKILL.md")} != {allowed}:
            raise ValueError("Wheel must contain exactly the template-owned update skill")
        if any(name.startswith(("tests/", "tools/")) for name in names):
            raise ValueError("Unexpected development files or skills in wheel")
        if "gzlite/resources/docs/engineering/architectural-decisions.md" not in names:
            raise ValueError("Wheel is missing the canonical ADR policy")
        for relative in (
            "bundle.json",
            ".agents/plugins/marketplace.json",
            ".claude-plugin/marketplace.json",
            "templates/AGENTS.skills-first.md",
            skill,
            "docs/engineering/architectural-decisions.md",
        ):
            content = archive.read(f"gzlite/resources/{relative}")
            if content != (ROOT / relative).read_bytes():
                raise ValueError(f"Wheel resource differs from authority: {relative}")
    with tarfile.open(sdist) as archive:
        names = archive.getnames()
        if not any(name.endswith("/tests/test_starter.py") for name in names):
            raise ValueError("Source distribution is missing adoption tests")
        for relative in (
            "examples/application_foundations/pyproject.toml",
            "examples/application_foundations/README.md",
            "examples/application_foundations/settings.example.json",
            "examples/application_foundations/src/example_foundations/configuration.py",
            ".github/dependabot.yml",
            "baselines/xplane/pyproject.toml",
            "baselines/xplane/uv.lock",
            "baselines/xplane/.python-version",
            "baselines/xplane/README.md",
            "tools/engineering/cognitive_qualification.py",
            "tools/engineering/cognitive_check.py",
            "tools/engineering/fixtures/cognitive-v1.json",
        ):
            if not any(name.endswith(f"/{relative}") for name in names):
                raise ValueError(f"Source distribution is missing baseline input: {relative}")
        if any("/.venv/" in name for name in names):
            raise ValueError("Source distribution contains a development environment")


def verify_extra_metadata(archive: zipfile.ZipFile) -> None:
    """Assert verification dependencies are selected through the extra only."""
    entry = next(name for name in archive.namelist() if name.endswith(".dist-info/METADATA"))
    metadata = BytesParser().parsebytes(archive.read(entry))
    dependencies = metadata.get_all("Requires-Dist", [])
    if metadata.get_all("Provides-Extra", []) != ["verification"] or len(dependencies) != 1:
        raise ValueError("Wheel has the wrong dependency/extra boundary")
    requirement, _, marker = dependencies[0].lower().replace("'", '"').partition(";")
    if requirement.strip() != "pyyaml==6.0.4" or marker.strip() != 'extra == "verification"':
        raise ValueError("Wheel does not declare the exact optional YAML parser")


def release_fixture(directory: Path, version: str) -> tuple[str, str, dict[str, str]]:
    """Serve an invented release through Git's normal origin lookup."""
    origin = directory / "fixture-origin"
    origin.mkdir()
    config = directory / "git-config" / "git" / "config"
    config.parent.mkdir(parents=True)
    env = {**clean_git_env(), "XDG_CONFIG_HOME": str(config.parent.parent)}

    def git(*args: str) -> str:
        return run(
            "git",
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.invalid",
            *args,
            cwd=origin,
            env=env,
        ).stdout.strip()

    git("init", "--quiet", "--initial-branch=main")
    (origin / "bundle.json").write_text(json.dumps({"template_version": version}), encoding="utf-8")
    git("add", "bundle.json")
    git("commit", "--quiet", "--message=Fixture release")
    pin = git("rev-parse", "HEAD")
    git("tag", "--annotate", f"v{version}", "--message=Fixture release")
    git("commit", "--quiet", "--allow-empty", "--message=Unpublished fixture")
    untagged = git("rev-parse", "HEAD")
    git("config", "--file", str(config), "--add", f"url.{origin.as_uri()}.insteadOf", ORIGIN)
    return pin, untagged, env


def verify_native_hosts(command: Path, directory: Path, pin: str, env: dict[str, str]) -> None:
    """Exercise new host configuration and repair from the installed artifact."""
    for host, config, surface in (
        ("claude", ".claude/settings.json", ".claude"),
        ("opencode", "opencode.json", ".agents"),
    ):
        target = directory / host
        target.mkdir()
        args = (
            str(command),
            "configure",
            "--project",
            str(target),
            "--host",
            host,
            "--starter-ref",
            pin,
        )
        run(*args, "--apply", cwd=directory, env=env)
        if not (target / config).is_file():
            raise ValueError(f"Installed helper omitted {host} configuration")
        if (target / surface / "skills/gzl-update/SKILL.md").read_bytes() != (
            ROOT / "templates/skills/gzl-update/SKILL.md"
        ).read_bytes():
            raise ValueError(f"Installed helper omitted {host} update skill")
        if json.loads(run(*args, "--apply", cwd=directory, env=env).stdout)["writes"]:
            raise ValueError(f"Installed {host} configuration is not idempotent")
        lock = (target / ".gzlite/bundle.lock.json").read_bytes()
        run(
            str(command),
            "localize",
            "--project",
            str(target),
            "--host",
            host,
            "--starter-ref",
            pin,
            "--apply",
            cwd=directory,
            env=env,
        )
        if (target / ".gzlite/bundle.lock.json").read_bytes() != lock:
            raise ValueError(f"Installed {host} scope repair changed adoption provenance")


def verify_policy_modes(command: Path, directory: Path, pin: str, env: dict[str, str]) -> None:
    """Verify both policy access forms from an installed wheel without a checkout."""
    source = (ROOT / "docs/engineering/architectural-decisions.md").read_bytes()
    for host in ("codex", "claude", "opencode"):
        for mode in ("link", "local"):
            target = directory / f"policy-{host}-{mode}"
            target.mkdir()
            args = (
                str(command),
                "configure",
                "--project",
                str(target),
                "--starter-ref",
                pin,
                "--host",
                host,
            )
            run(*args, "--adr-policy", mode, cwd=directory, env=env)
            if list(target.iterdir()):
                raise ValueError("Installed policy preview wrote files")
            run(*args, "--adr-policy", mode, "--apply", cwd=directory, env=env)
            local = target / ".gzlite/architectural-decisions.md"
            if mode == "local" and local.read_bytes() != source:
                raise ValueError("Installed local policy differs from the canonical bytes")
            if mode == "link" and local.exists():
                raise ValueError("Installed link mode created a policy copy")
            lock = json.loads((target / ".gzlite/bundle.lock.json").read_bytes())
            if lock["adr_policy"]["source_sha256"] != hashlib.sha256(source).hexdigest():
                raise ValueError("Installed policy provenance hash differs")
            if json.loads(run(*args, "--apply", cwd=directory, env=env).stdout)["writes"]:
                raise ValueError("Installed helper did not preserve policy selection")
            status = json.loads(
                run(str(command), "status", "--project", str(target), cwd=directory, env=env).stdout
            )
            if status["adr_policy"]["mode"] != mode or status["runtime_readiness"] != "unverified":
                raise ValueError("Installed policy status changed selection or claimed readiness")


def verify_state_directory(command: Path, directory: Path, pin: str, env: dict[str, str]) -> None:
    """Exercise legacy-state refusal and the canonical state folder with the installed helper."""
    target = directory / "relocation"
    target.mkdir()
    configure = (str(command), "configure", "--project", str(target), "--starter-ref", pin)
    status = (str(command), "status", "--project", str(target))
    current = target / ".gzlite"

    def refused(args: tuple[str, ...]) -> None:
        result = subprocess.run(
            args, cwd=directory, env=env, capture_output=True, text=True, check=False
        )
        if result.returncode != 2 or "run gzlite migrate" not in result.stderr:
            raise ValueError(f"Installed state check did not request migration: {result.stderr}")

    for name in (".gz-starter", ".skills-first"):
        legacy = target / name
        legacy.mkdir()
        marker = legacy / "bundle.lock.json"
        marker.write_bytes(b"legacy marker")
        refused((*configure, "--apply"))
        refused(status)
        if current.exists() or marker.read_bytes() != b"legacy marker":
            raise ValueError("Installed helper changed state during a refused legacy command")
        marker.unlink()
        legacy.rmdir()
    run(*configure, "--adr-policy", "local", "--apply", cwd=directory, env=env)
    if not (current / "bundle.lock.json").is_file():
        raise ValueError("Installed helper did not write the canonical state folder")
    if json.loads(run(*status, cwd=directory, env=env).stdout)["status"] != "configured":
        raise ValueError("Installed helper did not recognize a configured target")
    if json.loads(run(*configure, "--apply", cwd=directory, env=env).stdout)["writes"]:
        raise ValueError("Installed helper changed a configured target")


def verify_release_commands(
    command: Path, directory: Path, target: Path, pin: str, env: dict[str, str]
) -> None:
    """Run the bridge and maintenance commands through the installed wheel."""
    program = str(command)
    profile = json.loads(
        run(
            program, "project-settings", "inspect", "--project", str(target), cwd=directory, env=env
        ).stdout
    )
    if profile.get("profile") is not None:
        raise ValueError("Installed project-settings inferred an adopter profile")

    catalog = directory / "fixture-catalog"
    skill = catalog / "skills/gzs-fixture"
    (skill / "agents").mkdir(parents=True)
    (skill / "SKILL.md").write_text(
        "---\nname: gzs-fixture\ndescription: Invented skill.\n---\n\n"
        "## Discovery and fallback\n\nRead the project instructions.\n",
        encoding="utf-8",
    )
    (skill / "agents/openai.yaml").write_text(
        "policy:\n  allow_implicit_invocation: true\n", encoding="utf-8"
    )
    report = run(program, "catalog", "check", "--root", str(catalog), cwd=directory, env=env)
    if json.loads(report.stdout) != []:
        raise ValueError("Installed catalog check reported findings on the clean fixture")
    report = run(
        program,
        "portability",
        "--check",
        "subprocess-errors",
        "--root",
        str(catalog),
        cwd=directory,
        env=env,
    )
    if json.loads(report.stdout) != []:
        raise ValueError("Installed portability check reported findings on the clean fixture")

    legacy = directory / "fixture-legacy"
    old_state = legacy / ".gz-starter/bundle.lock.json"
    old_state.parent.mkdir(parents=True)
    old_state.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "starter": {
                    "repository": "https://github.com/tvproductions/gz-starter.git",
                    "version": "0.13.0",
                    "revision": "98acc5aeec3f3b6ad61171a647dbc0ab7a44b7c6",
                },
                "host": "codex",
                "components": json.loads((ROOT / "bundle.json").read_bytes())["components"],
            }
        ),
        encoding="utf-8",
    )
    before = old_state.read_bytes()
    ref = ("--starter-ref", pin)
    migration = json.loads(
        run(
            program,
            "migrate",
            "--project",
            str(legacy),
            *ref,
            cwd=directory,
            env=env,
        ).stdout
    )
    if migration["status"] != "preview" or not migration["fingerprint"]:
        raise ValueError("Installed migrate did not preview a reviewable adoption plan")
    if old_state.read_bytes() != before or (legacy / ".gzlite").exists():
        raise ValueError("Installed migrate preview wrote adopter state")

    refresh = json.loads(
        run(
            program,
            "freshen",
            "--project",
            str(target),
            *ref,
            cwd=directory,
            env=env,
        ).stdout
    )
    if refresh["status"] != "current" or refresh["writes"]:
        raise ValueError("Installed freshen did not recognize a current adopter")


def verify_fixture(sdist: Path) -> None:
    """Build the reference from delivered source and verify clean installed use."""
    with tempfile.TemporaryDirectory(prefix="starter-foundations-") as temporary:
        directory = Path(temporary)
        source = directory / "source"
        source.mkdir()
        with tarfile.open(sdist) as archive:
            top = archive.getnames()[0].split("/")[0]
            archive.extractall(source, filter="data")
        fixture = source / top / "examples/application_foundations"
        artifacts = directory / "artifacts"
        sentinel = secrets.token_hex(24)
        protected = directory / "protected-parent-output.txt"
        protected.write_text("parent environment must not change this", encoding="utf-8")
        parent_environment = dict(os.environ) | {
            "EXAMPLE_FOUNDATIONS_CONFIG": str(directory / "missing-parent-config.json"),
            "EXAMPLE_FOUNDATIONS_MESSAGE": "parent override must not load",
            "EXAMPLE_FOUNDATIONS_OUTPUT_FILE": str(protected),
        }
        clean = {
            key: value
            for key, value in parent_environment.items()
            if key not in ("PYTHONPATH", "PYTHONHOME")
            and not key.startswith("EXAMPLE_FOUNDATIONS_")
        }
        clean["EXAMPLE_FOUNDATIONS_TOKEN"] = sentinel
        run(
            "uv",
            "build",
            "--no-sources",
            "--project",
            str(fixture),
            "--out-dir",
            str(artifacts),
            cwd=directory,
            env=clean,
        )
        wheel = artifacts / "example_foundations-0.1.0-py3-none-any.whl"
        with zipfile.ZipFile(wheel) as archive:
            if "example_foundations/py.typed" not in archive.namelist():
                raise ValueError("Reference library is missing its typing marker")
            if any(sentinel.encode() in archive.read(name) for name in archive.namelist()):
                raise ValueError("Fixture distribution leaked a test credential")
        environment = directory / "env"
        run("uv", "venv", "--python", sys.executable, str(environment), cwd=directory, env=clean)
        scripts = environment / ("Scripts" if os.name == "nt" else "bin")
        python = scripts / ("python.exe" if os.name == "nt" else "python")
        command = scripts / (
            "example-foundations.exe" if os.name == "nt" else "example-foundations"
        )
        run(
            "uv",
            "pip",
            "install",
            "--offline",
            "--no-deps",
            "--python",
            str(python),
            str(wheel),
            cwd=directory,
            env=clean,
        )
        outside = directory / "outside"
        outside.mkdir()
        config_root = directory / "operator"
        config_root.mkdir()
        settings = config_root / "settings.json"
        settings.write_text(
            '{"schema_version":1,"message":"external settings survive"}', encoding="utf-8"
        )
        before = settings.read_bytes()
        arguments = (
            str(python),
            "-I",
            "-m",
            "example_foundations",
            "--config-root",
            str(config_root),
        )
        result = run(*arguments, cwd=outside, env=clean)
        if protected.read_text(encoding="utf-8") != "parent environment must not change this":
            raise ValueError("Installed fixture followed an inherited output override")
        if json.loads(result.stdout) != {"text": "external settings survive"}:
            raise ValueError("Installed reference did not load external settings")
        if run(str(command), "--version", cwd=outside, env=clean).stdout.strip() != "0.1.0":
            raise ValueError("Installed fixture entry point has the wrong version")
        run(
            str(python),
            "-I",
            "-c",
            "from example_foundations import load_settings, Settings, Overrides",
            cwd=outside,
            env=clean,
        )
        consumer = outside / "consumer.py"
        consumer.write_text(
            'from example_foundations import Settings\ncount: int = Settings("hello", 1, (), None).repeat\n',
            encoding="utf-8",
        )
        run(
            "uv",
            "run",
            "--locked",
            "ty",
            "check",
            "--python",
            str(python),
            str(consumer),
            cwd=ROOT,
            env=clean,
        )
        consumer.write_text(
            'from example_foundations import Settings\ncount: str = Settings("hello", 1, (), None).repeat\n',
            encoding="utf-8",
        )
        rejected = subprocess.run(
            ["uv", "run", "--locked", "ty", "check", "--python", str(python), str(consumer)],
            cwd=ROOT,
            env=clean,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        if (
            rejected.returncode != 1
            or "invalid-assignment" not in rejected.stdout + rejected.stderr
        ):
            raise ValueError("Installed reference types did not reject an invalid consumer")
        run(
            "uv",
            "pip",
            "install",
            "--offline",
            "--no-deps",
            "--reinstall",
            "--python",
            str(python),
            str(wheel),
            cwd=outside,
            env=clean,
        )
        if settings.read_bytes() != before:
            raise ValueError("Code replacement changed operator settings")
        run(*arguments, cwd=outside, env=clean)
        missing = subprocess.run(
            [*arguments, "--config", str(config_root / "missing.json")],
            cwd=outside,
            env=clean,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        if missing.returncode != 2 or missing.stdout:
            raise ValueError("Invalid explicit settings did not fail before output")
        settings.write_text(
            '{"schema_version":1,"credential_ref":"env:EXAMPLE_FOUNDATIONS_TOKEN"}',
            encoding="utf-8",
        )
        clean["EXAMPLE_FOUNDATIONS_TOKEN"] = sentinel
        diagnostics = run(*arguments, "--check-config", cwd=outside, env=clean)
        if clean["EXAMPLE_FOUNDATIONS_TOKEN"] in diagnostics.stdout + diagnostics.stderr:
            raise ValueError("Installed reference leaked an injected credential")


def write_verification_fixture(project: Path, wheel: Path) -> dict[Path, bytes]:
    """Seed an invented existing adopter using the actual packaged workflow."""
    project.mkdir()
    sources = {
        "README.md": "# Sample totals\n\n[Handoff](docs/handoff.md).\n",
        "docs/handoff.md": "# Handoff\n\nRuntime design awaits project approval.\n",
        ".gitignore": ".venv/\n__pycache__/\n",
        ".python-version": (ROOT / ".python-version").read_text(encoding="utf-8"),
        "pyproject.toml": (
            '[project]\nname = "sample-totals"\nversion = "0.1.0"\nreadme = "README.md"\n'
            'requires-python = ">=3.14,<3.15"\n\n'
            '[tool.uv]\npackage = false\nrequired-version = ">=0.13.5"\n'
            'python-preference = "only-managed"\n\n'
            '[tool.gz-starter.verify]\ntop_level = "."\n'
        ),
        ".pre-commit-config.yaml": (
            "repos:\n  - repo: local\n    hooks:\n"
            "      - id: unittest\n        name: unittest and bootstrap verification\n"
            "        entry: uv run --locked gz-starter verify --project .\n"
            "        language: system\n        pass_filenames: false\n"
            "        always_run: true\n        stages: [pre-commit]\n"
        ),
    }
    with zipfile.ZipFile(wheel) as archive:
        sources[".github/workflows/verify-python.yml"] = archive.read(WORKFLOW).decode("utf-8")
    paths = {}
    for name, content in sources.items():
        path = project / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")
        paths[path] = path.read_bytes()
    return paths


def assert_verification_fault(
    project: Path, command: tuple[str, ...], expected: str, env: dict[str, str]
) -> None:
    """Require a nonzero result that reached the intended verification fault."""
    result = subprocess.run(
        command,
        cwd=project,
        env=env,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    output = result.stdout + result.stderr
    if result.returncode != 1 or expected not in output or "bootstrap PASS" in output:
        raise ValueError(
            f"Expected verification failure {expected!r}, got {result.returncode}: {output}"
        )


def verify_installed_verification(
    wheel: Path, base_command: Path, directory: Path, pin: str, release_env: dict[str, str]
) -> None:
    """Exercise base and extra installs through the adopter command and hook."""
    env = {
        key: value
        for key, value in release_env.items()
        if key not in {"PYTHONPATH", "PYTHONHOME", "UV_PROJECT_ENVIRONMENT", "VIRTUAL_ENV", "SKIP"}
        and not key.startswith("GIT_")
    }
    project = directory / "verification-adopter"
    preserved = write_verification_fixture(project, wheel)
    assert_verification_fault(
        project,
        (str(base_command), "verify", "--project", "."),
        "install gzlite[verification]",
        env,
    )
    run(
        "uv",
        "add",
        "--dev",
        f"gzlite[verification] @ {wheel.as_uri()}",
        "pre-commit==4.7.0",
        "coverage==7.17.5",
        cwd=project,
        env=env,
    )
    for name in ("pyproject.toml", "uv.lock"):
        path = project / name
        preserved[path] = path.read_bytes()
    prefix = ("uv", "run", "--locked")
    configure = (*prefix, "gz-starter", "configure", "--project", ".", "--starter-ref", pin)
    run(*configure, cwd=project, env=env)
    if any(path.read_bytes() != expected for path, expected in preserved.items()):
        raise ValueError("Installed preview changed adopter files")
    run(*configure, "--apply", cwd=project, env=env)
    provenance = project / ".gzlite/bundle.lock.json"
    preserved[provenance] = provenance.read_bytes()
    repeated = run(*configure, "--apply", cwd=project, env=env)
    if json.loads(repeated.stdout)["writes"]:
        raise ValueError("Installed adoption failed the existing-adopter no-op check")
    if any(path.read_bytes() != expected for path, expected in preserved.items()):
        raise ValueError("Installed configure changed existing adopter files or provenance")
    run("git", "init", cwd=project, env=env)
    run("git", "add", ".", cwd=project, env=env)
    run("uv", "sync", "--locked", cwd=project, env=env)
    verify_installed_hook(project, env)
    if any(path.read_bytes() != expected for path, expected in preserved.items()):
        raise ValueError("Installed verification changed existing adopter files")


def verify_installed_hook(project: Path, env: dict[str, str]) -> None:
    """Exercise the unchanged adopter hook and preserve an existing coverage failure."""
    prefix = ("uv", "run", "--locked")
    check = (*prefix, "gz-starter", "verify", "--project", ".")
    gate = (*prefix, "pre-commit", "run", "--all-files")
    bootstrap = run(*check, cwd=project, env=env)
    if "not applicable: pre-implementation" not in bootstrap.stdout:
        raise ValueError("Installed verifier did not report the real bootstrap status")
    run(*gate, cwd=project, env=env)
    (project / "totals.py").write_text(
        "def combine(a, b):\n    if a > 0:\n        return a + b\n    return b\n",
        encoding="utf-8",
    )
    assert_verification_fault(project, gate, "missing unittest start directory", env)
    tests = project / "tests"
    tests.mkdir()
    (tests / "__init__.py").touch()
    test = tests / "test_totals.py"
    template = (
        "import unittest\nfrom totals import combine\n"
        "class TotalsTests(unittest.TestCase):\n"
        "    def test_combines_values(self):\n"
        "        self.assertEqual(combine(2, 3), {expected}, 'reached installed test')\n"
    )
    test.write_text(template.format(expected=6), encoding="utf-8")
    assert_verification_fault(project, gate, "reached installed test", env)
    test.write_text(template.format(expected=5), encoding="utf-8")
    if "behavior PASS" not in run(*check, cwd=project, env=env).stdout:
        raise ValueError("Installed verifier did not confirm adopter-owned behavior")
    run(*gate, cwd=project, env=env)
    hidden = tests / "unimportable"
    hidden.mkdir()
    missed = hidden / "test_missed.py"
    missed.write_text(template.format(expected=6), encoding="utf-8")
    assert_verification_fault(project, gate, "test_missed.py", env)
    missed.unlink()
    hidden.rmdir()
    skipped = template.format(expected=5).replace(
        "    def test_combines_values",
        "    @unittest.skip('fixture skip')\n    def test_combines_values",
    )
    test.write_text(skipped, encoding="utf-8")
    assert_verification_fault(project, gate, "no successful adopter test", env)
    test.write_text(template.format(expected=5), encoding="utf-8")
    run(*gate, cwd=project, env=env)
    assert_existing_coverage_failure(project, env)


def assert_existing_coverage_failure(project: Path, env: dict[str, str]) -> None:
    prefix = ("uv", "run", "--locked", "coverage")
    run(
        *prefix,
        "run",
        "--source=totals",
        "--branch",
        "-m",
        "unittest",
        "discover",
        "-s",
        "tests",
        "-t",
        ".",
        cwd=project,
        env=env,
    )
    report = subprocess.run(
        [*prefix, "report", "--fail-under=100"],
        cwd=project,
        env=env,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if report.returncode != 2 or "Coverage failure" not in report.stdout:
        raise ValueError("Installed adopter coverage gate lost its failing outcome")


def main() -> None:
    """Inspect archives and exercise the installed helper outside the checkout."""
    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    version = metadata["project"]["version"]
    distribution = metadata["project"]["name"].replace("-", "_")
    wheel = ROOT / "dist" / f"{distribution}-{version}-py3-none-any.whl"
    sdist = ROOT / "dist" / f"{distribution}-{version}.tar.gz"
    verify_archives(wheel, sdist)
    verify_fixture(sdist)
    with tempfile.TemporaryDirectory(prefix="starter-wheel-") as temporary:
        directory = Path(temporary)
        environment = directory / "env"
        run("uv", "venv", "--python", sys.executable, str(environment), cwd=directory)
        scripts = environment / ("Scripts" if os.name == "nt" else "bin")
        python = scripts / ("python.exe" if os.name == "nt" else "python")
        command = scripts / ("gzlite.exe" if os.name == "nt" else "gzlite")
        run(
            "uv",
            "pip",
            "install",
            "--offline",
            "--no-deps",
            "--python",
            str(python),
            str(wheel),
            cwd=directory,
        )
        run(str(command), "validate", cwd=directory)
        for alias in ("gz-starter", "skills-first-starter"):
            bridge = scripts / (f"{alias}.exe" if os.name == "nt" else alias)
            if (
                run(str(bridge), "version", cwd=directory).stdout
                != run(str(command), "version", cwd=directory).stdout
            ):
                raise ValueError(f"Bridge alias {alias} differs from the canonical command")
        result = run(str(python), "-I", "-m", "gzlite", "version", cwd=directory)
        if json.loads(result.stdout)["template_version"] != version:
            raise ValueError("Installed version differs from project metadata")
        pin, untagged, release_env = release_fixture(directory, version)
        target = directory / "adopter"
        target.mkdir()
        unpublished = subprocess.run(
            [
                str(command),
                "configure",
                "--project",
                str(target),
                "--starter-ref",
                untagged,
                "--apply",
            ],
            cwd=directory,
            env=release_env,
            capture_output=True,
            text=True,
            check=False,
        )
        if (
            unpublished.returncode != 2
            or untagged not in unpublished.stderr
            or list(target.iterdir())
        ):
            raise ValueError("Installed helper accepted or wrote files for an unpublished pin")
        args = (str(command), "configure", "--project", str(target), "--starter-ref", pin)
        run(*args, cwd=directory, env=release_env)
        if list(target.iterdir()):
            raise ValueError("Installed preview wrote project files")
        run(*args, "--apply", cwd=directory, env=release_env)
        if (target / ".agents/skills/gzl-update/SKILL.md").read_bytes() != (
            ROOT / "templates/skills/gzl-update/SKILL.md"
        ).read_bytes():
            raise ValueError("Installed helper did not seed the canonical update skill")
        repeated = json.loads(run(*args, "--apply", cwd=directory, env=release_env).stdout)
        if repeated["writes"]:
            raise ValueError("Installed repeated adoption was not a no-op")
        status = json.loads(
            run(
                str(command), "status", "--project", str(target), cwd=directory, env=release_env
            ).stdout
        )
        if status["runtime_readiness"] != "unverified":
            raise ValueError("Installed helper falsely claimed runtime readiness")
        verify_native_hosts(command, directory, pin, release_env)
        verify_policy_modes(command, directory, pin, release_env)
        verify_state_directory(command, directory, pin, release_env)
        verify_release_commands(command, directory, target, pin, release_env)
        refused = subprocess.run(
            [str(command), "configure", "--project", str(target)],
            cwd=directory,
            text=True,
            encoding="utf-8",
            errors="strict",
            capture_output=True,
            check=False,
        )
        if refused.returncode != 2:
            raise ValueError("Installed helper inferred provenance outside a starter checkout")
        verify_installed_verification(wheel, command, directory, pin, release_env)
    print("Wheel resources, sdist contents and isolated installed CLI checks passed.")


if __name__ == "__main__":
    main()
