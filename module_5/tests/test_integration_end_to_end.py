"""End-to-end flows: pull -> update -> render.

Rubric: "Integration Tests" (8 pts).
"""

import re

import pytest
from bs4 import BeautifulSoup
from sqlalchemy import func, select

from models import Applicant

pytestmark = pytest.mark.integration

TWO_DECIMAL_PERCENT = re.compile(r"\d+\.\d{2}%")
ANY_PERCENT = re.compile(r"\d+(?:\.\d+)?%")


def _count(session_factory):
    with session_factory() as session:
        return session.scalar(select(func.count()).select_from(Applicant))


def test_pull_update_render_round_trip(db_client, clean_db, fake_rows):
    """Fake scraper returns multiple records; rows land in the DB and reach the page."""
    pull = db_client.post("/pull-data")
    assert pull.status_code in (200, 202)
    assert _count(clean_db) == len(fake_rows)

    update = db_client.post("/update-analysis")
    assert update.status_code == 200
    assert update.get_json()["total"] == len(fake_rows)

    page = db_client.get("/analysis")
    assert page.status_code == 200
    text = BeautifulSoup(page.get_data(as_text=True), "html.parser").get_text(" ", strip=True)
    assert "Answer:" in text


def test_rendered_analysis_updates_and_formats_values(db_client, clean_db, fake_rows):
    """After the round trip the page shows updated values, still two-decimal formatted."""
    db_client.post("/pull-data")
    db_client.post("/update-analysis")

    soup = BeautifulSoup(db_client.get("/analysis").get_data(as_text=True), "html.parser")
    dek = soup.select_one(".dek")
    assert dek is not None
    assert f"{len(fake_rows)} self-reported results" in dek.get_text(" ", strip=True)

    percentages = ANY_PERCENT.findall(soup.get_text(" ", strip=True))
    assert percentages
    assert all(TWO_DECIMAL_PERCENT.fullmatch(p) for p in percentages), percentages


def test_multiple_pulls_with_overlapping_data_stay_consistent(db_client, clean_db, fake_rows):
    """Two pulls over overlapping records leave the uniqueness policy intact."""
    db_client.post("/pull-data")
    db_client.post("/pull-data")
    assert _count(clean_db) == len(fake_rows)
