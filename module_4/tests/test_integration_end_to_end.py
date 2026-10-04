"""End-to-end flows: pull -> update -> render.

Rubric: "Integration Tests" (8 pts).
"""

import pytest

pytestmark = pytest.mark.integration


def test_pull_update_render_round_trip(client, clean_db, fake_scraper):
    """Fake scraper returns multiple records; rows land in the DB and reach the page."""
    pytest.skip("TODO: POST /pull-data -> POST /update-analysis -> GET /analysis")


def test_rendered_analysis_updates_and_formats_values(client, clean_db):
    """After the round trip the page shows updated values, still two-decimal formatted."""
    pytest.skip("TODO")


def test_multiple_pulls_with_overlapping_data_stay_consistent(client, clean_db):
    """Two pulls over overlapping records leave the uniqueness policy intact."""
    pytest.skip("TODO")
