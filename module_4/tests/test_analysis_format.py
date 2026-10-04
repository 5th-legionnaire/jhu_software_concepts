"""Analysis labelling and percentage formatting.

Rubric: "Analysis Formatting and Database Tests" (formatting portion, 5 pts).
"""

import re

import pytest
from bs4 import BeautifulSoup

from query_data import fmt_avg, fmt_count, fmt_diff, fmt_pct

pytestmark = pytest.mark.analysis

TWO_DECIMAL_PERCENT = re.compile(r"\d+\.\d{2}%")
ANY_PERCENT = re.compile(r"\d+(?:\.\d+)?%")


def test_rendered_items_are_labeled_with_answer(client):
    """Every rendered analysis item carries an "Answer:" label."""
    soup = BeautifulSoup(client.get("/analysis").get_data(as_text=True), "html.parser")
    labels = soup.select(".answer-label")
    assert labels, "no Answer: labels were rendered"
    assert all(label.get_text(strip=True) == "Answer:" for label in labels)
    # One label per rendered value: labelling is consistent, not incidental.
    assert len(labels) == len(soup.select(".value"))


def test_percentages_render_with_exactly_two_decimals(client):
    """Any percentage on the page matches a two-decimal pattern, e.g. 39.28%."""
    text = BeautifulSoup(client.get("/analysis").get_data(as_text=True),
                          "html.parser").get_text(" ", strip=True)
    percentages = ANY_PERCENT.findall(text)
    assert percentages, "no percentages were rendered to check"
    assert all(TWO_DECIMAL_PERCENT.fullmatch(p) for p in percentages), percentages


def test_formatting_helpers_round_to_two_decimals():
    """fmt_pct / fmt_avg round rather than truncate, including near-boundary values."""
    # Chosen just off the halfway point between cents, so float representation
    # cannot make the expected rounding ambiguous.
    assert fmt_pct(39.284999) == "39.28%"
    assert fmt_pct(39.285001) == "39.29%"
    assert fmt_avg(3.144999) == "3.14"
    assert fmt_avg(3.145001) == "3.15"
    assert fmt_pct(None) == "n/a"
    assert fmt_avg(None) == "n/a"
    assert fmt_count(19290) == "19,290"
    assert fmt_diff(3) == "+3"
    assert fmt_diff(-2) == "-2"
    assert fmt_diff(0) == "0"
