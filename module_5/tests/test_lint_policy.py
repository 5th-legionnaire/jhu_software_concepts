"""Repository policy: every collected test carries a registered marker (CHG-18).

EN 605.256 Modern Software Concepts in Python, Module 5.
Joshua Latz (jlatz1)

Module 4 selected tests with a marker expression, so a test carrying only a
marker missing from that expression would silently never run. Module 5 runs
the whole suite and conftest.py refuses to start if any test is unmarked.
These tests pin that policy: the hook's logic is checked on fake items, and
the live session is checked directly, so deleting the hook alone does not let
an unmarked test through. scripts/gate.sh proves the same thing end to end by
adding an unmarked dummy test and confirming the run fails.
"""

import configparser
import re
import subprocess
import sys
from pathlib import Path

import pytest

import conftest

pytestmark = pytest.mark.security

EXPECTED_MARKERS = {"web", "buttons", "analysis", "db", "integration", "security"}


class _FakeItem:
    """Just enough of a pytest Item for the policy functions."""

    def __init__(self, nodeid, markers):
        self.nodeid = nodeid
        self._markers = markers

    def get_closest_marker(self, name):
        """Truthy when the item carries the named marker, like pytest's own."""
        return name if name in self._markers else None


def test_every_collected_test_is_marked(request):
    """Every test in this session carries one of the registered markers."""
    items = request.session.items
    assert items, "no tests collected; the check below would be vacuous"
    assert conftest.unmarked_items(items, conftest.registered_markers(request.config)) == []


def test_registered_markers_are_the_rubric_five_plus_security(request):
    assert conftest.registered_markers(request.config) == EXPECTED_MARKERS


def test_unmarked_items_reports_only_tests_without_an_allowed_marker():
    """A parametrize mark is not a category marker, so it does not count."""
    items = [
        _FakeItem("tests/test_a.py::test_marked", {"web"}),
        _FakeItem("tests/test_a.py::test_bare", set()),
        _FakeItem("tests/test_a.py::test_param_only", {"parametrize"}),
    ]
    assert conftest.unmarked_items(items, EXPECTED_MARKERS) == [
        "tests/test_a.py::test_bare",
        "tests/test_a.py::test_param_only",
    ]


def test_collection_hook_rejects_an_unmarked_test_by_name(request):
    items = [_FakeItem("tests/test_a.py::test_marked", {"db"}),
             _FakeItem("tests/test_a.py::test_bare", set())]
    with pytest.raises(pytest.UsageError, match="test_bare"):
        conftest.pytest_collection_modifyitems(request.config, items)


def test_collection_hook_accepts_a_fully_marked_session(request):
    items = [_FakeItem("tests/test_a.py::test_marked", {"security"})]
    assert conftest.pytest_collection_modifyitems(request.config, items) is None


# --- Module 5: the lint policy relaxes nothing (CHG-17, decision D6) ----------

MODULE_DIR = Path(__file__).resolve().parent.parent


def test_pylintrc_relaxes_nothing():
    """The file says where the code lives and classifies SQLAlchemy bases. It silences nothing."""
    parser = configparser.ConfigParser()
    parser.read(MODULE_DIR / ".pylintrc", encoding="utf-8")
    assert {section: set(parser[section]) for section in parser.sections()} == {
        "MAIN": {"source-roots"},
        "DESIGN": {"exclude-too-few-public-methods"},
    }
    assert parser["MAIN"]["source-roots"] == "src"
    assert parser["DESIGN"]["exclude-too-few-public-methods"] == "sqlalchemy.orm.*"


@pytest.mark.parametrize("forbidden", ["disable", "max-line-length", "max-args", "max-locals",
                                       "max-attributes", "fail-under", "ignore", "ignore-patterns"])
def test_pylintrc_sets_no_threshold_or_exclusion(forbidden):
    text = (MODULE_DIR / ".pylintrc").read_text(encoding="utf-8")
    assert not re.search(rf"^\s*{forbidden}\s*=", text, re.MULTILINE)


def test_no_inline_disables():
    """Findings are fixed in the code. Nothing in src/ or the scripts silences Pylint."""
    marker = re.compile(r"#\s*pylint\s*:\s*(disable|skip-file)", re.IGNORECASE)
    offenders = [f"{path.name}:{number}"
                 for path in sorted((MODULE_DIR / "src").glob("*.py"))
                 for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
                 if marker.search(line)]
    assert offenders == []


def test_the_inline_disable_check_would_catch_one():
    marker = re.compile(r"#\s*pylint\s*:\s*(disable|skip-file)", re.IGNORECASE)
    assert marker.search("x = 1  # " + "pylint: " + "disable=line-too-long")
    assert marker.search("# " + "pylint:" + "skip-file")
    assert not marker.search("# the pylint score is ten")


def test_pylint_scores_ten_with_no_messages():
    """The actual rubric number: no message of any kind, and exactly 10.00/10."""
    result = subprocess.run(
        [sys.executable, "-m", "pylint", "--rcfile=.pylintrc", "--fail-under=10", "src"],
        cwd=MODULE_DIR, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stdout[-800:]
    assert "rated at 10.00/10" in result.stdout
    assert not re.search(r"^src/\S+:\d+:\d+: [CRWEF]\d{4}", result.stdout, re.MULTILINE)
