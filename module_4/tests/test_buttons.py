"""Button endpoints and busy-state gating.

Rubric: "Flask Page and Button Behavior Tests" (13 pts) and "Busy-State,
Error-Path, and Deterministic Behavior Tests" (8 pts).
"""

import pytest

from app import create_app

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
    broken = create_app(scraper=failing_scraper, loader=fake_loader,
                         database_url=db_url, testing=True)
    response = broken.test_client().post("/pull-data")
    assert response.status_code != 200
    assert response.get_json()["ok"] is False
    assert fake_loader.calls == []
