"""Analysis labelling and percentage formatting.

Rubric: "Analysis Formatting and Database Tests" (formatting portion, 5 pts).
"""

import pytest

pytestmark = pytest.mark.analysis


def test_rendered_items_are_labeled_with_answer(client):
    """Every rendered analysis item carries an "Answer:" label."""
    pytest.skip("TODO")


def test_percentages_render_with_exactly_two_decimals(client):
    """Any percentage on the page matches a two-decimal pattern, e.g. 39.28%."""
    pytest.skip(r"TODO: regex r'\d+\.\d{2}%' over the rendered page, assert no stragglers")


def test_formatting_helpers_round_to_two_decimals():
    """fmt_pct / fmt_avg round rather than truncate, including .005 boundaries."""
    pytest.skip("TODO: unit-test query_data.fmt_pct, fmt_avg, fmt_count, fmt_diff directly")
