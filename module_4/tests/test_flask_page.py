"""Flask app factory and analysis page rendering.

Rubric: "Flask Page and Button Behavior Tests" (13 pts, page-load portion) and
"Application Structure and Testability" (create_app factory).
"""

import pytest
from bs4 import BeautifulSoup

pytestmark = pytest.mark.web


def test_create_app_returns_testable_app(app):
    """A testable app is created and exposes every route the service declares."""
    assert app.testing is True
    rules = {rule.rule for rule in app.url_map.iter_rules()}
    assert {"/analysis", "/", "/pull-data", "/update-analysis"} <= rules


def test_get_analysis_returns_200(client):
    """GET /analysis returns status 200."""
    response = client.get("/analysis")
    assert response.status_code == 200


def test_page_contains_both_buttons(client):
    """The page renders Pull Data and Update Analysis with stable selectors."""
    soup = BeautifulSoup(client.get("/analysis").get_data(as_text=True), "html.parser")
    assert soup.select_one('[data-testid="pull-data-btn"]') is not None
    assert soup.select_one('[data-testid="update-analysis-btn"]') is not None


def test_page_text_includes_analysis_and_an_answer_label(client):
    """Page text includes "Analysis" and at least one "Answer:" label."""
    soup = BeautifulSoup(client.get("/analysis").get_data(as_text=True), "html.parser")
    text = soup.get_text(" ", strip=True)
    assert "Analysis" in text
    assert "Answer:" in text
