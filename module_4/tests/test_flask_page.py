"""Flask app factory and analysis page rendering.

Rubric: "Flask Page and Button Behavior Tests" (13 pts, page-load portion) and
"Application Structure and Testability" (create_app factory).
"""

import pytest

pytestmark = pytest.mark.web


def test_create_app_returns_testable_app(app):
    """A testable app is created and exposes every route the service declares."""
    pytest.skip("TODO: assert app.testing and that /, /pull-data, /update-analysis are registered")


def test_get_analysis_returns_200(client):
    """GET /analysis returns status 200."""
    pytest.skip("TODO")


def test_page_contains_both_buttons(client):
    """The page renders Pull Data and Update Analysis with stable selectors."""
    pytest.skip('TODO: assert data-testid="pull-data-btn" and data-testid="update-analysis-btn"')


def test_page_text_includes_analysis_and_an_answer_label(client):
    """Page text includes "Analysis" and at least one "Answer:" label."""
    pytest.skip("TODO: parse with BeautifulSoup, not substring matching")
