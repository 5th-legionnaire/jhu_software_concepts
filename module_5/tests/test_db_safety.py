"""db_safety: limit clamping, strict limit parsing, and text validation (CHG-07).

EN 605.256 Modern Software Concepts in Python, Module 5.
Joshua Latz (jlatz1)

These functions sit between request text and SQL, so the tests are boundary
tables: the values on either side of every edge, and the hostile inputs the
malicious-input matrix later sends through the API. Every rejection must say
which field was wrong and must not repeat what was sent.
"""

import pytest

import db_safety as safety

pytestmark = pytest.mark.security


@pytest.mark.parametrize("value, expected", [
    (None, 20),                # the default
    (-(10 ** 9), 1), (-1, 1), (0, 1),   # below the minimum
    (1, 1), (2, 2), (20, 20), (99, 99), (100, 100),   # the valid range, edges included
    (101, 100), (10 ** 9, 100),         # above the maximum
])
def test_clamp_boundaries(value, expected):
    assert safety.clamp_limit(value) == expected


def test_clamp_uses_the_caller_default_only_for_none_and_still_clamps_it():
    assert safety.clamp_limit(None, default=7) == 7
    assert safety.clamp_limit(None, default=500) == 100
    assert safety.clamp_limit(0, default=7) == 1


def test_limit_constants_are_the_rubric_range():
    assert (safety.MIN_LIMIT, safety.MAX_LIMIT, safety.DEFAULT_LIMIT) == (1, 100, 20)


@pytest.mark.parametrize("raw, expected", [
    (None, (20, False)),                 # absent: the default, not a clamp
    ("20", (20, False)), ("1", (1, False)), ("100", (100, False)),
    ("+5", (5, False)), ("007", (7, False)),
    ("0", (1, True)), ("-5", (1, True)), ("-0", (1, True)),
    ("101", (100, True)), ("1000000", (100, True)), ("999999999", (100, True)),
])
def test_parse_limit_accepts_and_reports_whether_it_clamped(raw, expected):
    assert safety.parse_limit(raw) == expected


@pytest.mark.parametrize("raw", [
    "", " ", "abc", "1e3", "1.5", "0x10", "10 OR 1=1", "5; DROP TABLE applicants", "' OR '1'='1",
    " 5", "5 ", "5\n", "\n5", "--5", "+-5", "1_000",
    "1000000000",                        # ten digits
    "9" * 5000,                          # never reaches int()
    "١٢",                      # Arabic-Indic digits: int() would accept them
    "５",                            # full-width digit five
    "5\x00", "%00",
])
def test_parse_limit_rejects(raw):
    with pytest.raises(safety.LimitError) as caught:
        safety.parse_limit(raw)
    assert "limit" in str(caught.value)
    assert raw.strip() == "" or raw not in str(caught.value), "the message echoed the input"


def test_limit_error_is_an_input_error_so_one_handler_covers_both():
    assert issubclass(safety.LimitError, safety.InputError)
    assert issubclass(safety.InputError, ValueError)


@pytest.mark.parametrize("raw", [None, ""])
def test_validate_text_treats_absent_and_empty_as_no_filter(raw):
    assert safety.validate_text(raw, "term", 64) is None


@pytest.mark.parametrize("raw", [
    "Fall 2026", "O'Brien", "' OR '1'='1", "100%", "a_b", "back\\slash",     # SQL-looking text is data
    "مرحبا", "שלום",             # right-to-left scripts
    "\U0001f393 grad", "café", "中文",                            # emoji, accents, CJK
])
def test_validate_text_returns_acceptable_text_unchanged(raw):
    assert safety.validate_text(raw, "term", 64) == raw


def test_validate_text_accepts_exactly_max_len_and_rejects_one_more():
    assert safety.validate_text("a" * 64, "term", 64) == "a" * 64
    with pytest.raises(safety.InputError, match="term must be at most 64 characters"):
        safety.validate_text("a" * 65, "term", 64)


def test_validate_text_rejects_a_ten_thousand_character_value():
    with pytest.raises(safety.InputError, match="at most 64"):
        safety.validate_text("A" * 10000, "term", 64)


@pytest.mark.parametrize("raw", [
    "a\x00b", "\x00", "a\x01b", "tab\there", "line\nbreak", "cr\rhere", "\x7f", "\x1b[31m",
    "\u0085",                            # next line, a C1 control
    "\ud800",                            # a lone surrogate
])
def test_validate_text_rejects_control_characters_and_surrogates(raw):
    with pytest.raises(safety.InputError, match="parameter contains a control character"):
        safety.validate_text(raw, "parameter", 64)


def test_validate_text_rejects_nul_without_echoing_it():
    with pytest.raises(safety.InputError) as caught:
        safety.validate_text("secret\x00value", "nationality", 64)
    assert "secret" not in str(caught.value)
    assert "nationality" in str(caught.value)


def test_validate_text_error_names_the_field_and_not_the_value():
    with pytest.raises(safety.InputError) as caught:
        safety.validate_text("x" * 200, "q", 100)
    assert str(caught.value) == "q must be at most 100 characters"
