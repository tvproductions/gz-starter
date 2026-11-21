"""Run and account for the adopter's unittest suite in its locked uv environment."""

from __future__ import annotations

import ast
import fnmatch
import json
import subprocess
import sys
import tempfile
import unittest
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, cast


@dataclass(frozen=True)
class DiscoverySelection:
    """One standard unittest discovery selection."""

    start: str = "tests"
    pattern: str = "test*.py"
    top_level: str | None = None


def _directory(root: Path, raw: str, label: str) -> Path:
    relative = Path(raw)
    destination = (root / relative).resolve()
    if (
        not raw
        or relative.is_absolute()
        or relative.drive
        or " " in raw
        or not destination.is_relative_to(root)
        or destination.relative_to(root).parts[:1] in {(".git",), (".venv",)}
    ):
        raise ValueError(f"unittest {label} must be a project-local directory")
    return destination


def discovery_selection(root: Path, data: dict[str, Any]) -> DiscoverySelection:
    """Validate configuration in both bootstrap and implementation checkouts."""
    if set(data) - {"start", "pattern", "top_level"} or any(
        not isinstance(value, str) for value in data.values()
    ):
        raise ValueError("unittest selection supports only string start, pattern and top_level")
    selection = DiscoverySelection(**data)
    start = _directory(root, selection.start, "start")
    if selection.top_level is not None:
        top = _directory(root, selection.top_level, "top_level")
        if not start.is_relative_to(top):
            raise ValueError("unittest start must be inside top_level")
    if not selection.pattern or any(sep in selection.pattern for sep in ("/", "\\")):
        raise ValueError("unittest pattern must be a filename glob")
    return selection


def _suite_cases(suite):
    if isinstance(suite, unittest.TestCase):
        yield suite
    else:
        for item in suite:
            yield from _suite_cases(item)


def _owner(test: unittest.TestCase) -> Path | None:
    module = sys.modules.get(type(test).__module__)
    source = getattr(module, "__file__", None)
    return Path(source).resolve() if source else None


class OwningLoader(unittest.TestLoader):
    """Record local package aggregators reached by discovery."""

    def __init__(self):
        super().__init__()
        self.aggregates: dict[Path, tuple[Path | None, ...]] = {}

    def loadTestsFromModule(self, module, *, pattern=None):
        suite = super().loadTestsFromModule(module, pattern=pattern)
        source = getattr(module, "__file__", None)
        if source and Path(source).name == "__init__.py" and hasattr(module, "load_tests"):
            self.aggregates[Path(source).resolve()] = tuple(
                _owner(case) for case in _suite_cases(suite)
            )
        return suite


class OwningResult(unittest.TextTestResult):
    """Count confirmed successes rather than inferring success from test counts."""

    def __init__(self, stream, descriptions, verbosity):
        super().__init__(stream, descriptions, verbosity)
        self.successes: list[unittest.TestCase] = []
        self.started: list[unittest.TestCase] = []

    def startTest(self, test):
        super().startTest(test)
        self.started.append(test)

    def addSuccess(self, test):
        super().addSuccess(test)
        self.successes.append(test)


def _test_class_names(tree: ast.Module) -> set[str]:
    classes = set()
    supported = {"TestCase", "IsolatedAsyncioTestCase"}
    modules = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            modules.update(
                alias.asname or alias.name for alias in node.names if alias.name == "unittest"
            )
        elif isinstance(node, ast.ImportFrom) and node.module in {"unittest", "unittest.case"}:
            classes.update(
                alias.asname or alias.name for alias in node.names if alias.name in supported
            )
    classes.update(f"{module}.{name}" for module in modules for name in supported)
    return classes


def _declares_test(tree: ast.Module) -> bool:
    classes = _test_class_names(tree)
    for node in tree.body:
        if not isinstance(node, ast.ClassDef) or not any(
            ast.unparse(base) in classes for base in node.bases
        ):
            continue
        classes.add(node.name)
        if any(
            isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef))
            and method.name.startswith("test")
            for method in node.body
        ):
            return True
    return False


def _binds_load_tests(node: ast.stmt) -> bool:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return node.name == "load_tests"
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        return any((alias.asname or alias.name) == "load_tests" for alias in node.names)
    targets: list[ast.expr] = []
    if isinstance(node, ast.Assign):
        targets = node.targets
    elif isinstance(node, ast.AnnAssign):
        targets = [node.target]
    return any(
        isinstance(part, ast.Name) and part.id == "load_tests" and isinstance(part.ctx, ast.Store)
        for target in targets
        for part in ast.walk(target)
    )


def _declarations(root: Path, path: Path) -> tuple[bool, bool]:
    try:
        tree = ast.parse((root / path).read_bytes(), filename=path.as_posix())
    except SyntaxError, UnicodeError, ValueError:
        # Keep this module visible. Discovery supplies the actual import error.
        return True, False
    return _declares_test(tree), any(_binds_load_tests(node) for node in tree.body)


def _test_candidates(
    root: Path, selection: DiscoverySelection, python_paths: set[Path]
) -> tuple[set[Path], set[Path]]:
    start = _directory(root, selection.start, "start").relative_to(root)
    patterns = ("test*.py", "*_test.py", selection.pattern)
    candidates = set()
    aggregators = set()
    for path in sorted(python_paths):
        conventional = any(fnmatch.fnmatchcase(path.name, pattern) for pattern in patterns)
        test, hook = (False, False)
        if path.is_relative_to(start) or path.is_relative_to("tests"):
            test, hook = _declarations(root, path)
        if conventional or test or hook:
            candidates.add(root / path)
        if hook and not test and path.name == "__init__.py":
            aggregators.add(root / path)
    return candidates, aggregators


def _missing_tests(
    root: Path,
    loader: OwningLoader,
    collected: tuple[unittest.TestCase, ...],
    candidates: set[Path],
    aggregators: set[Path],
    python_paths: set[Path],
) -> set[Path]:
    owners = {_owner(case) for case in collected}
    if any(owner is None or not owner.is_relative_to(root) for owner in owners):
        raise ValueError("unittest suite contains tests from outside the checkout")
    if any(owner is not None and owner.relative_to(root) not in python_paths for owner in owners):
        raise ValueError("unittest suite contains tests outside the inventoried adopter modules")
    accounted = set(owners)
    for path in aggregators:
        owned_children = loader.aggregates.get(path, ())
        if owned_children and all(
            owner is not None
            and owner in owners
            and owner.is_relative_to(path.parent)
            and owner != path
            for owner in owned_children
        ):
            accounted.add(path)
    return candidates - accounted


def run_adopter_tests(root: Path, selection: DiscoverySelection, paths: tuple[Path, ...]) -> int:
    """Launch the discovery process with the target project's actual locked Python."""
    request = {
        "selection": {key: value for key, value in asdict(selection).items() if value is not None},
        "paths": [path.as_posix() for path in paths if path.suffix == ".py"],
    }
    # A same-size edit at the cached timestamp can otherwise execute stale tests.
    with tempfile.TemporaryDirectory(prefix="gz-verifier-bytecode-") as cache:
        result = subprocess.run(
            [
                "uv",
                "run",
                "--locked",
                "--project",
                str(root),
                "--managed-python",
                "python",
                "-I",
                "-B",
                "-X",
                f"pycache_prefix={cache}",
                str(Path(__file__).resolve()),
            ],
            cwd=root,
            input=json.dumps(request).encode("utf-8"),
            check=False,
        )
    return 0 if result.returncode == 0 else 1


def main() -> int:
    """Run the isolated child and keep its local import paths out of the caller."""
    try:
        request = json.load(sys.stdin)
        root = Path.cwd().resolve()
        selection = discovery_selection(root, request["selection"])
        pin = (root / ".python-version").read_text(encoding="utf-8").strip()
        actual = ".".join(map(str, sys.version_info[:3]))
        if sys.implementation.name != "cpython" or actual != pin:
            raise ValueError(f"test interpreter {actual} does not match the project pin {pin}")
        python_paths = {Path(path) for path in request["paths"]}
        return _run_suite(root, selection, python_paths)
    except (ImportError, OSError, TypeError, ValueError, RecursionError) as error:
        print(f"verification blocked: {error}", file=sys.stderr)
        return 1


def _run_suite(root: Path, selection: DiscoverySelection, paths: set[Path]) -> int:
    start = _directory(root, selection.start, "start")
    if not start.is_dir():
        raise ValueError(
            f"adopter tests are required: missing unittest start directory {selection.start}"
        )
    top = _directory(root, selection.top_level, "top_level") if selection.top_level else None
    candidates, aggregators = _test_candidates(root, selection, paths)
    sys.path.insert(0, str(root))
    loader = OwningLoader()
    suite = loader.discover(str(start), selection.pattern, str(top) if top else None)
    if loader.errors:
        for error in loader.errors:
            print(error, file=sys.stderr)
        return 1
    collected = tuple(_suite_cases(suite))
    missing = _missing_tests(root, loader, collected, candidates, aggregators, paths)
    if missing:
        names = ", ".join(path.relative_to(root).as_posix() for path in sorted(missing))
        raise ValueError(f"unittest discovery did not collect owned cases from: {names}")
    runner = unittest.TextTestRunner(verbosity=2, resultclass=OwningResult)
    result = cast("OwningResult", runner.run(suite))
    if not result.wasSuccessful():
        return 1
    identities = {id(case) for case in collected}
    if any(id(case) not in identities for case in (*result.started, *result.successes)):
        raise ValueError("unittest suite ran tests outside the collected adopter cases")
    if not result.successes:
        raise ValueError("no successful adopter test was recorded")
    print(f"behavior PASS; {len(result.successes)} successful adopter test(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
