"""Button endpoints and busy-state gating.

Rubric: "Flask Page and Button Behavior Tests" (13 pts) and "Busy-State,
Error-Path, and Deterministic Behavior Tests" (8 pts).
"""

import psycopg
import pytest
from selenium.common.exceptions import WebDriverException
from sqlalchemy.exc import SQLAlchemyError

import app as app_module
from app import Services, create_app
from pull_data import PullError

pytestmark = pytest.mark.buttons


def test_post_pull_data_returns_ok_when_not_busy(client, fake_loader, fake_rows):
    """POST /pull-data returns 200/202 with {"ok": true} and calls the loader."""
    response = client.post("/pull-data")
    assert response.status_code in (200, 202)
    assert response.get_json()["ok"] is True
    assert fake_loader.calls == [fake_rows]


def test_post_update_analysis_returns_200_when_not_busy(client):
    """POST /update-analysis returns 200 and refreshes the analysis."""
    response = client.post("/update-analysis")
    assert response.status_code == 200
    assert response.get_json()["ok"] is True


def test_update_analysis_is_gated_while_busy(app, client):
    """While a pull is in progress, POST /update-analysis returns 409 {"busy": true}."""
    app.config["PULL_STATE"].busy = True
    response = client.post("/update-analysis")
    assert response.status_code == 409
    assert response.get_json()["busy"] is True


def test_pull_data_is_gated_while_busy(app, client):
    """While a pull is in progress, a second POST /pull-data returns 409."""
    app.config["PULL_STATE"].busy = True
    response = client.post("/pull-data")
    assert response.status_code == 409
    assert response.get_json()["busy"] is True


def test_busy_gate_performs_no_update(app, client, fake_loader):
    """A gated request writes nothing: the loader is never called."""
    app.config["PULL_STATE"].busy = True
    client.post("/pull-data")
    assert fake_loader.calls == []


def test_loader_failure_yields_non_200_and_no_partial_write(failing_scraper, fake_loader, db_url):
    """Negative path: a scraper/loader error returns non-200 and leaves no rows.

    Built directly with create_app() rather than the shared app fixture: the
    app fixture's scraper is already fixed to fake_scraper, so there is no
    way to swap in failing_scraper through it.
    """
    broken = create_app(Services(scraper=failing_scraper, loader=fake_loader),
                        database_url=db_url, testing=True)
    response = broken.test_client().post("/pull-data")
    assert response.status_code != 200
    assert response.get_json()["ok"] is False
    assert fake_loader.calls == []


def test_post_pull_data_returns_202_when_the_runner_defers(fake_scraper, fake_loader,
                                                            fake_query, db_url):
    """A non-testing app's runner starts a background pull and returns None
    immediately; the route must answer 202, not wait for a result to report."""
    deferred = create_app(
        Services(scraper=fake_scraper, loader=fake_loader, query=fake_query,
                 runner=lambda job: None),
        database_url=db_url, testing=True)
    response = deferred.test_client().post("/pull-data")

    assert response.status_code == 202
    assert response.get_json() == {"ok": True, "started": True}


def test_update_analysis_returns_503_when_the_database_is_unreachable(fake_scraper, fake_loader,
                                                                       db_url):
    def _raising_query():
        raise SQLAlchemyError("connection refused")

    broken = create_app(
        Services(scraper=fake_scraper, loader=fake_loader, query=_raising_query),
        database_url=db_url, testing=True)
    response = broken.test_client().post("/update-analysis")

    assert response.status_code == 503
    assert response.get_json()["ok"] is False


# --- Module 5: a failed pull must never leave the app stuck busy (CHG-10) ----

def _app_with(scraper, db_url, fake_loader):
    return create_app(Services(scraper=scraper, loader=fake_loader),
                      database_url=db_url, testing=True)


def _raises(error):
    def _scrape():
        raise error
    return _scrape


@pytest.mark.parametrize("failure", [
    PullError("scrape failed"),
    psycopg.OperationalError("down"),
    SQLAlchemyError("down"),
    OSError("disk full"),
    WebDriverException("browser crashed"),
], ids=["PullError", "psycopg", "SQLAlchemy", "OSError", "WebDriver"])
def test_every_anticipated_failure_is_a_json_500_and_clears_busy(db_url, fake_loader, failure):
    app = _app_with(_raises(failure), db_url, fake_loader)
    response = app.test_client().post("/pull-data")

    assert response.status_code == 500
    assert response.get_json()["ok"] is False
    assert "Pull Data stopped." in response.get_json()["error"]
    assert app.config["PULL_STATE"].busy is False
    assert app.config["PULL_STATE"].last["state"] == "failed"


def test_unlisted_exception_clears_busy(db_url, fake_loader):
    """The trap: an error nobody anticipated must not leave busy True, or every later pull is a 409."""
    app = _app_with(_raises(RuntimeError("a bug nobody listed")), db_url, fake_loader)
    app.config["PROPAGATE_EXCEPTIONS"] = False
    client = app.test_client()

    assert client.post("/pull-data").status_code == 500
    state = app.config["PULL_STATE"]
    assert state.busy is False
    assert state.last["state"] == "failed"
    assert "unexpected error" in state.last["text"]

    # And the very next pull is accepted, not refused with a 409.
    assert client.post("/pull-data").status_code == 500


def test_unhandled_error_returns_json_500(db_url, fake_loader):
    """An error outside the anticipated set reaches the handler, which answers in the usual shape."""
    app = _app_with(_raises(RuntimeError("a bug")), db_url, fake_loader)
    app.config["PROPAGATE_EXCEPTIONS"] = False
    response = app.test_client().post("/pull-data")

    assert response.status_code == 500
    assert response.is_json
    body = response.get_json()
    assert body == {"ok": False, "error": app_module.UNEXPECTED_ERROR}
    assert "a bug" not in str(body), "the exception's text must not reach the client"


def test_the_500_handler_covers_every_route(client):
    """The handler is the app's, not the pull route's."""
    registered = client.application.error_handler_spec[None][500]
    assert registered, "no 500 handler is registered"


def test_a_successful_pull_after_a_failure_is_accepted(db_url, fake_loader, fake_rows):
    """Busy is not sticky: a failed pull and then a good one is the normal recovery."""
    calls = []

    def flaky():
        calls.append(1)
        if len(calls) == 1:
            raise PullError("first try fails")
        return fake_rows

    app = _app_with(flaky, db_url, fake_loader)
    client = app.test_client()
    assert client.post("/pull-data").status_code == 500
    assert client.post("/pull-data").status_code == 200
    assert app.config["PULL_STATE"].last["state"] == "succeeded"
