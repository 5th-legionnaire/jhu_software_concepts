"""Button endpoints and busy-state gating.

Rubric: "Flask Page and Button Behavior Tests" (13 pts) and "Busy-State,
Error-Path, and Deterministic Behavior Tests" (8 pts).
"""

import pytest

pytestmark = pytest.mark.buttons


def test_post_pull_data_returns_ok_when_not_busy(client, fake_loader):
    """POST /pull-data returns 200/202 with {"ok": true} and calls the loader."""
    pytest.skip("TODO: assert status in (200, 202), payload ok is True, fake_loader.calls")


def test_post_update_analysis_returns_200_when_not_busy(client):
    """POST /update-analysis returns 200 and refreshes the analysis."""
    pytest.skip("TODO")


def test_update_analysis_is_gated_while_busy(client):
    """While a pull is in progress, POST /update-analysis returns 409 {"busy": true}."""
    pytest.skip("TODO: set the busy flag through injectable state, never sleep()")


def test_pull_data_is_gated_while_busy(client):
    """While a pull is in progress, a second POST /pull-data returns 409."""
    pytest.skip("TODO")


def test_busy_gate_performs_no_update(client, fake_loader):
    """A gated request writes nothing: the loader is never called."""
    pytest.skip("TODO")


def test_loader_failure_yields_non_200_and_no_partial_write(app, failing_scraper):
    """Negative path: a scraper/loader error returns non-200 and leaves no rows."""
    pytest.skip("TODO: build an app with failing_scraper injected")
