"""Packaging and the dependency lock (CHG-01, CHG-02).

EN 605.256 Modern Software Concepts in Python, Module 5.
Joshua Latz (jlatz1)

setup.py is the single source of dependencies and requirements.txt is a lock
generated from it. These tests pin the properties that make that arrangement
safe. The installed modules resolve to src/ without any sys.path edit. Every
src/ module is declared. The lock pins everything, including the tooling and
the transitive runtime packages that "uv pip sync" would otherwise silently
omit. And the lock still satisfies setup.py's ranges, which catches an edit to
setup.py that was never followed by scripts/regen_lock.sh.

setup.py is read with ast rather than imported, because importing it would
run setup().
"""

import ast
import importlib
import importlib.metadata
import re
from pathlib import Path

import pytest
from packaging.requirements import Requirement

pytestmark = pytest.mark.security

MODULE_DIR = Path(__file__).resolve().parent.parent
SRC = MODULE_DIR / "src"
SETUP_PY = MODULE_DIR / "setup.py"
LOCK = MODULE_DIR / "requirements.txt"
CONFTEST = MODULE_DIR / "tests" / "conftest.py"

PINNED_LINE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*(\[[A-Za-z0-9,._-]+\])?==[^\s;]+( ; .+)?$")


def _normalize(name):
    """PEP 503 normalized project name, so "PyYAML" matches "pyyaml"."""
    return re.sub(r"[-_.]+", "-", name).lower()


def _setup_literals():
    """The list literals assigned at setup.py's top level, plus setup()'s py_modules."""
    tree = ast.parse(SETUP_PY.read_text(encoding="utf-8"))
    values = {node.targets[0].id: ast.literal_eval(node.value)
              for node in tree.body
              if isinstance(node, ast.Assign) and isinstance(node.value, ast.List)}
    call = next(node for node in ast.walk(tree)
                if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "setup")
    for keyword in call.keywords:
        if keyword.arg == "py_modules":
            values["py_modules"] = ast.literal_eval(keyword.value)
    return values


def _lock_lines():
    """Requirement lines of the lock, without comments or blank lines."""
    return [line.strip() for line in LOCK.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")]


def _lock_versions():
    """{normalized name: pinned version} from the lock.

    An unpinned line is left out here rather than raising, so that
    test_lock_pins_every_line is the test that names it.
    """
    pins = {}
    for line in _lock_lines():
        requirement = Requirement(line)
        exact = [spec.version for spec in requirement.specifier if spec.operator == "=="]
        if exact:
            pins[_normalize(requirement.name)] = exact[0]
    return pins


def test_modules_import_from_installed_location():
    """Each declared module imports from module_5/src through the editable install."""
    assert importlib.metadata.version("gradcafe-analytics") == "5.0.0"
    for name in _setup_literals()["py_modules"]:
        module = importlib.import_module(name)
        assert Path(module.__file__).resolve().parent == SRC, name


def test_setup_py_declares_every_src_module():
    """A new src/ module that setup.py forgets would import in tests but not when installed."""
    assert sorted(_setup_literals()["py_modules"]) == sorted(p.stem for p in SRC.glob("*.py"))


def test_no_sys_path_mutation_in_conftest():
    tree = ast.parse(CONFTEST.read_text(encoding="utf-8"))
    uses = [node.lineno for node in ast.walk(tree)
            if isinstance(node, ast.Attribute) and node.attr == "path"
            and isinstance(node.value, ast.Name) and node.value.id == "sys"]
    assert uses == [], f"conftest.py touches sys.path on line(s) {uses}"


def test_lock_pins_every_line():
    lines = _lock_lines()
    assert lines
    unpinned = [line for line in lines if not PINNED_LINE.match(line)]
    assert unpinned == []


def test_lock_includes_tooling():
    """The assignment requires pylint and pydeps in requirements.txt."""
    pins = _lock_versions()
    for tool in ("pylint", "pydeps", "pytest", "pytest-cov"):
        assert tool in pins, tool


def test_lock_includes_transitive_runtime():
    """Flask's own dependencies must be pinned, or "uv pip sync" builds an app that cannot start."""
    pins = _lock_versions()
    for package in ("werkzeug", "jinja2", "markupsafe", "itsdangerous", "psycopg-binary"):
        assert package in pins, package


def test_lock_satisfies_setup_py_ranges():
    """Every runtime and dev requirement is pinned, at a version inside its declared range."""
    literals = _setup_literals()
    pins = _lock_versions()
    for spec in literals["RUNTIME"] + literals["DEV"]:
        requirement = Requirement(spec)
        name = _normalize(requirement.name)
        assert name in pins, f"{name} is declared in setup.py but missing from the lock"
        assert requirement.specifier.contains(pins[name]), \
            f"{name}=={pins[name]} is outside setup.py's {requirement.specifier}"
