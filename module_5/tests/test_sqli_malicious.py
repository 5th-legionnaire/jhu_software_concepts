"""The malicious-input matrix for GET /api/applicants, against a real database.

EN 605.256 Modern Software Concepts in Python, Module 5.
Joshua Latz (jlatz1)

Each case sends hostile input through the real route, the real validation, and
the real psycopg search against a seeded disposable database. Every case
asserts the same four things, whatever it sends:

    1. the status is not 500 (hostile input is refused or harmless, never a crash);
    2. the applicants table still holds all N seeded rows (nothing was dropped
       or changed);
    3. every returned row has exactly the projection's columns, so no column
       from another table can appear;
    4. nothing slow or sensitive came back (checked per case where it matters).

The rows are seeded so that "everything was returned" is distinguishable from a
correct empty or partial answer: hostile filters must match 0 rows, not N.
"""

import time

import pytest
from psycopg import sql

import applicant_search as search
import load_data as ld
from app import Services, create_app

pytestmark = [pytest.mark.db, pytest.mark.security]

SEEDS = [
    # url id, program, term, status, degree, nationality
    (9100001, "Computer Science, Johns Hopkins University", "Fall 2026", "Accepted", "Masters", "American"),
    (9100002, "100% Match University", "Fall 2026", "Rejected", "PhD", "International"),
    (9100003, "Under_score College", "Fall 2026", "Accepted", "PhD", "American"),
    (9100004, "Back\\slash Institute", "Spring 2027", "Interview", "Masters", "International"),
    (9100005, "Universität Zürich \U0001f393", "Spring 2027", "Accepted", "PhD", "American"),
]
N = len(SEEDS)
AMERICANS = sum(1 for seed in SEEDS if seed[5] == "American")


def _record(url_id, program, term, status, degree, nationality):
    """One record in the Module 2 JSON key format."""
    return {
        "url": f"https://www.thegradcafe.com/result/{url_id}", "program": program,
        "program_name": program, "university": program, "comments": "seeded",
        "date_added": "Sep 12, 2026", "status": status, "decision_date": "Sep 10",
        "term": term, "US/International": nationality, "GRE": "GRE 165", "GRE V": "GRE V 160",
        "GRE AW": "GRE AW 4.5", "GPA": "GPA 3.80", "Degree": degree,
        "llm-generated-program": program, "llm-generated-university": program,
    }


@pytest.fixture
def seeded(clean_db, db_url):
    """The real app over a database holding exactly N known rows, and a row counter."""
    connection = ld.create_connection(ld.get_db_config(db_url))
    ld.insert_records(connection, [_record(*seed) for seed in SEEDS])

    def count():
        with connection.cursor() as cursor:
            cursor.execute(sql.SQL("SELECT COUNT(*) FROM applicants LIMIT {n}").format(
                n=sql.Placeholder("n")), {"n": 1})
            return cursor.fetchone()[0]

    assert count() == N
    app = create_app(Services(), database_url=db_url, testing=True)
    yield app.test_client(), count
    connection.close()


def _get(seeded, query):
    """Send the query, then check the four invariants every case shares."""
    client, count = seeded
    response = client.get("/api/applicants", query_string=query)
    assert response.status_code != 500, response.get_data(as_text=True)[:200]
    assert count() == N, "the applicants table changed"
    body = response.get_json()
    for row in body.get("rows", []):
        assert set(row) == set(search.PROJECTION)
    return response, body


# --- hostile filter values: a 200 with nothing matched ----------------------

@pytest.mark.parametrize("query", [
    [("term", "' OR '1'='1")],
    [("term", "Fall 2026'; DROP TABLE applicants; --")],
    [("status", "accepted' UNION SELECT usename, passwd FROM pg_shadow --")],
    [("degree", "phd' OR 1=1 --")],
    [("nationality", "american'; DELETE FROM applicants; --")],
    [("q", "' OR '1'='1")],
    [("q", "x'; DROP TABLE applicants; --")],
    [("term", "Fall 2026"), ("status", "' OR ''='")],
], ids=["term-or-true", "term-drop-table", "status-union-pg_shadow", "degree-or-1=1",
        "nationality-delete", "q-or-true", "q-drop-table", "two-filters-one-hostile"])
def test_hostile_filter_values_match_nothing_and_change_nothing(seeded, query):
    response, body = _get(seeded, query)
    assert response.status_code == 200
    assert body["rows"] == [] and body["count"] == 0, "a hostile filter returned rows"
    assert "passwd" not in response.get_data(as_text=True)
    assert "usename" not in response.get_data(as_text=True)


# --- LIKE wildcards are data -------------------------------------------------

@pytest.mark.parametrize("query, program", [
    ([("q", "%")], "100% Match University"),
    ([("q", "_")], "Under_score College"),
    ([("q", "\\")], "Back\\slash Institute"),
    ([("q", "100%")], "100% Match University"),
    ([("q", "under_score")], "Under_score College"),
    ([("q", "UNDER_SCORE")], "Under_score College"),
], ids=["percent", "underscore", "backslash", "percent-prefix", "underscore-name", "case-insensitive"])
def test_like_wildcards_match_only_literally(seeded, query, program):
    response, body = _get(seeded, query)
    assert response.status_code == 200
    assert [row["program"] for row in body["rows"]] == [program]


def test_a_plain_q_still_matches_normally(seeded):
    _, body = _get(seeded, [("q", "university")])
    programs = sorted(row["program"] for row in body["rows"])
    assert programs == ["100% Match University", "Computer Science, Johns Hopkins University"]


# --- rejected input: a 400, never a crash -----------------------------------

@pytest.mark.parametrize("query", [
    [("sort", "gpa; DROP TABLE applicants")],
    [("sort", 'p_id"')],
    [("sort", "gpa), (SELECT pg_sleep(5)")],
    [("order", "desc; SELECT pg_sleep(5)")],
    [("limit", "abc")], [("limit", "1e3")], [("limit", "10 OR 1=1")], [("limit", "9" * 5000)],
    [("term", "\x00")],
    [("term", "A" * 10000)],
    [("debug", "1")],
    [("limit", "5"), ("password", "x")],
], ids=["sort-drop", "sort-quote", "sort-subquery", "order-sleep", "limit-abc", "limit-1e3",
        "limit-or", "limit-5000-digits", "nul-byte", "10000-chars", "unknown-debug", "unknown-password"])
def test_rejected_input_is_a_400(seeded, query):
    response, body = _get(seeded, query)
    assert response.status_code == 400
    assert body["ok"] is False


def test_a_sleep_injection_attempt_is_refused_quickly(seeded):
    started = time.perf_counter()
    response, _ = _get(seeded, [("order", "desc; SELECT pg_sleep(5)")])
    assert response.status_code == 400
    assert time.perf_counter() - started < 2


# --- the limit --------------------------------------------------------------

def test_an_enormous_limit_is_clamped_to_the_maximum(seeded):
    response, body = _get(seeded, [("limit", "1000000")])
    assert response.status_code == 200
    assert body["limit"] == 100 and body["count"] <= 100 and body["clamped"] is True
    assert body["requested_limit"] == "1000000"
    assert body["count"] == N


@pytest.mark.parametrize("raw", ["0", "-5"])
def test_a_limit_below_the_minimum_is_raised_to_one(seeded, raw):
    response, body = _get(seeded, [("limit", raw)])
    assert response.status_code == 200
    assert body["limit"] == 1 and body["count"] == 1 and body["clamped"] is True


def test_an_in_range_limit_is_honored_and_not_marked_clamped(seeded):
    _, body = _get(seeded, [("limit", "3")])
    assert (body["limit"], body["count"], body["clamped"]) == (3, 3, False)


# --- legitimate but unusual input: literal, and never a crash ---------------

def test_unicode_and_emoji_are_matched_literally(seeded):
    response, body = _get(seeded, [("q", "Universität Zürich \U0001f393")])
    assert response.status_code == 200 and body["count"] == 1


@pytest.mark.parametrize("value", ["مرحبا", "שלום",
                                   "\U0001f393\U0001f393", "‮evil‬"])
def test_right_to_left_text_and_emoji_are_data(seeded, value):
    response, body = _get(seeded, [("term", value)])
    assert response.status_code == 200 and body["rows"] == []


def test_the_first_of_a_repeated_parameter_wins(seeded):
    response, body = _get(seeded, [("nationality", "american"), ("nationality", "' OR 1=1 --")])
    assert response.status_code == 200
    assert body["count"] == AMERICANS
    assert {row["us_or_international"] for row in body["rows"]} == {"American"}


# --- ordinary use works -----------------------------------------------------

def test_filters_are_case_insensitive_and_combine(seeded):
    _, body = _get(seeded, [("term", "FALL 2026"), ("status", "accepted"), ("degree", "masters")])
    assert [row["p_id"] for row in body["rows"]] == [9100001]


@pytest.mark.parametrize("sort, order, first", [
    ("p_id", "asc", 9100001), ("p_id", "desc", 9100005),
])
def test_sort_and_order_apply(seeded, sort, order, first):
    _, body = _get(seeded, [("sort", sort), ("order", order)])
    assert body["rows"][0]["p_id"] == first
    assert body["sort"] == sort and body["order"] == order


@pytest.mark.parametrize("sort", search.SORT_COLUMNS)
def test_every_whitelisted_sort_column_executes(seeded, sort):
    response, body = _get(seeded, [("sort", sort)])
    assert response.status_code == 200 and body["count"] == N


def test_dates_are_returned_as_iso_text(seeded):
    _, body = _get(seeded, [("limit", "1")])
    assert body["rows"][0]["date_added"] == "2026-09-12"
