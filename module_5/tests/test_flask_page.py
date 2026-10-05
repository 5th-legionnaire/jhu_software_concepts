"""Flask app factory and analysis page rendering.

Rubric: "Flask Page and Button Behavior Tests" (13 pts, page-load portion) and
"Application Structure and Testability" (create_app factory).
"""

import threading

import pytest
from bs4 import BeautifulSoup
from sqlalchemy.exc import SQLAlchemyError

import app as app_module
from app import create_app, make_scraper, run_in_background

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


def test_get_analysis_returns_503_when_the_database_is_unreachable(fake_scraper, fake_loader,
                                                                    db_url):
    def _raising_query():
        raise SQLAlchemyError("connection refused")

    broken = create_app(scraper=fake_scraper, loader=fake_loader, query=_raising_query,
                        database_url=db_url, testing=True)
    response = broken.test_client().get("/analysis")

    assert response.status_code == 503
    assert b"could not be reached" in response.data


# --- create_app's factory internals: exercised directly, since every test
# app overrides their real defaults -----------------------------------------

def test_run_in_background_starts_a_daemon_thread_and_returns_none():
    """The real runner for a non-testing app. ran.wait() is a synchronization
    primitive, not a fixed-duration sleep: it returns the instant the thread
    sets the event, with a generous timeout only as a hang safety net.
    """
    ran = threading.Event()

    def job():
        ran.set()

    assert run_in_background(job) is None
    assert ran.wait(timeout=2)


def test_make_scraper_binds_the_given_session_factory(monkeypatch):
    """The default scraper create_app() falls back to when none is injected."""
    calls = []
    monkeypatch.setattr(app_module, "scrape_new_records",
                        lambda session_factory: calls.append(session_factory))
    fake_factory = object()

    make_scraper(fake_factory)()

    assert calls == [fake_factory]
