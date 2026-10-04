"""Database writes, uniqueness, and the query contract.

Rubric: "Analysis Formatting and Database Tests" (database portion, 9 pts).
"""

import pytest
from sqlalchemy import func, select

from load_data import create_connection, get_db_config, insert_records
from models import Applicant
from orm_queries import REQUIRED_FIELDS, fetch_one

pytestmark = pytest.mark.db


def _count(session_factory):
    with session_factory() as session:
        return session.scalar(select(func.count()).select_from(Applicant))


def test_target_table_is_empty_before_pull(clean_db):
    """Before: the applicants table is empty."""
    assert _count(clean_db) == 0


def test_pull_inserts_rows_with_required_non_null_fields(db_client, clean_db, fake_rows):
    """After POST /pull-data, new rows exist with the Module 3 schema populated."""
    response = db_client.post("/pull-data")
    assert response.status_code in (200, 202)
    assert _count(clean_db) == len(fake_rows)

    with clean_db() as session:
        rows = session.scalars(select(Applicant)).all()
    assert len(rows) == len(fake_rows)
    for row in rows:
        for field in REQUIRED_FIELDS:
            assert getattr(row, field) is not None, f"{field} was not set on {row!r}"


def test_duplicate_pull_does_not_duplicate_rows(db_client, clean_db, fake_rows):
    """Idempotency: pulling the same data twice respects the uniqueness policy."""
    first = db_client.post("/pull-data")
    second = db_client.post("/pull-data")
    assert first.status_code in (200, 202)
    assert second.status_code in (200, 202)
    assert _count(clean_db) == len(fake_rows)


def test_query_function_returns_expected_keys(clean_db, fake_rows, db_url):
    """The query function returns a dict with the keys the analysis template uses."""
    connection = create_connection(get_db_config(db_url))
    try:
        insert_records(connection, fake_rows)
    finally:
        connection.close()

    with clean_db() as session:
        result = fetch_one(session)

    assert result is not None
    assert set(result.keys()) == set(REQUIRED_FIELDS)
