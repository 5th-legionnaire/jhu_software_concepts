"""Database writes, uniqueness, and the query contract.

Rubric: "Analysis Formatting and Database Tests" (database portion, 9 pts).
"""

import pytest

pytestmark = pytest.mark.db


def test_target_table_is_empty_before_pull(clean_db):
    """Before: the applicants table is empty."""
    pytest.skip("TODO")


def test_pull_inserts_rows_with_required_non_null_fields(client, clean_db):
    """After POST /pull-data, new rows exist with the Module 3 schema populated."""
    pytest.skip("TODO: assert required fields are non-null, not merely that rows exist")


def test_duplicate_pull_does_not_duplicate_rows(client, clean_db):
    """Idempotency: pulling the same data twice respects the uniqueness policy."""
    pytest.skip("TODO")


def test_query_function_returns_expected_keys(clean_db):
    """The query function returns a dict with the keys the analysis template uses."""
    pytest.skip("TODO: assert the exact Module 3 required key set")
