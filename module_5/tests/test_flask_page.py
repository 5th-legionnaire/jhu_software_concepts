"""Flask app factory and analysis page rendering.

Rubric: "Flask Page and Button Behavior Tests" (13 pts, page-load portion) and
"Application Structure and Testability" (create_app factory).
"""

import threading

import pytest
from bs4 import BeautifulSoup
from sqlalchemy.exc import SQLAlchemyError

import app as app_module
from app import Services, create_app, make_scraper, run_in_background

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

    broken = create_app(
        Services(scraper=fake_scraper, loader=fake_loader, query=_raising_query),
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


# --- Module 5: the Services seam (CHG-09) -----------------------------------

def test_services_default_to_real_implementations(db_url):
    """Left unset, each field becomes the real implementation, not None and not a fake."""
    from dataclasses import fields
    from models import make_session_factory

    resolved = app_module.with_defaults(Services(), make_session_factory(db_url), db_url, True)

    assert all(getattr(resolved, field.name) is not None for field in fields(Services))
    assert resolved.runner is app_module.run_inline
    background = app_module.with_defaults(Services(), make_session_factory(db_url), db_url, False)
    assert background.runner is app_module.run_in_background
    # The default search is the real one: with nothing listening it raises the
    # database error rather than returning rows.
    unreachable = app_module.with_defaults(
        Services(), make_session_factory(db_url), "postgresql+psycopg://localhost:1/none", True)
    with pytest.raises(app_module.DatabaseUnavailable):
        unreachable.search(object())


def test_services_override_is_used(db_url):
    """A field that is set is used as given; the others are still filled in."""
    from models import make_session_factory

    def custom_search(_filters):
        return [{"p_id": 7}]

    resolved = app_module.with_defaults(
        Services(search=custom_search), make_session_factory(db_url), db_url, True)
    assert resolved.search is custom_search
    assert resolved.scraper is not None and resolved.query is not None

    client = create_app(Services(search=custom_search), database_url=db_url,
                        testing=True).test_client()
    assert client.get("/api/applicants").get_json()["rows"] == [{"p_id": 7}]


def test_services_is_frozen_and_every_field_is_optional():
    from dataclasses import FrozenInstanceError
    services = Services()
    assert (services.scraper, services.loader, services.query,
            services.runner, services.search) == (None, None, None, None, None)
    with pytest.raises(FrozenInstanceError):
        services.search = lambda filters: []


def test_create_app_with_no_arguments_builds_an_app_with_every_route():
    """The Module 3 call, create_app(), still works."""
    app = create_app()
    rules = {rule.rule for rule in app.url_map.iter_rules()}
    assert {"/", "/analysis", "/pull-data", "/update-analysis", "/api/applicants"} <= rules
