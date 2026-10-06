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
