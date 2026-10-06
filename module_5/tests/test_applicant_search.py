"""GET /api/applicants: contract, validation, composition (CHG-08).

EN 605.256 Modern Software Concepts in Python, Module 5.
Joshua Latz (jlatz1)

Everything here runs offline. Validation is checked through the real Flask
route with a search that fails the test if it is ever called, which proves a
rejected request is refused before any query exists. Composition is checked by
rendering the statement with as_string(None). What the database does with
hostile input is test_sqli_malicious.py.
"""

import pytest
from psycopg import sql
from werkzeug.datastructures import MultiDict

import applicant_search as search
import app as app_module
from app import Services, create_app
from db_safety import InputError

pytestmark = [pytest.mark.web, pytest.mark.security]


def _must_not_run(_filters):
    pytest.fail("a rejected request reached the search")


def _client(fake_search, db_url):
    return create_app(Services(search=fake_search), database_url=db_url, testing=True).test_client()


def _filters(**overrides):
    """A SearchFilters with the defaults parse_search_args() would give."""
    text = overrides.pop("text", {})
    base = {"limit": 20, "requested_limit": None, "clamped": False, "sort": "date_added",
            "order": "desc", "text": text}
    return search.SearchFilters(**{**base, **overrides})


# --- parsing ----------------------------------------------------------------

def test_defaults_when_no_parameters_are_given():
    parsed = search.parse_search_args(MultiDict())
    assert (parsed.limit, parsed.requested_limit, parsed.clamped) == (20, None, False)
    assert (parsed.sort, parsed.order, dict(parsed.text)) == ("date_added", "desc", {})


def test_every_documented_parameter_is_parsed():
    args = MultiDict([("limit", "5"), ("sort", "gpa"), ("order", "asc"), ("term", "Fall 2026"),
                      ("status", "Accepted"), ("degree", "PhD"), ("nationality", "American"),
                      ("q", "stanford")])
    parsed = search.parse_search_args(args)
    assert (parsed.limit, parsed.sort, parsed.order) == (5, "gpa", "asc")
    assert dict(parsed.text) == {"term": "Fall 2026", "status": "Accepted", "degree": "PhD",
                                 "nationality": "American", "q": "stanford"}


def test_the_first_value_of_a_repeated_parameter_wins():
    args = MultiDict([("nationality", "american"), ("nationality", "' OR 1=1 --"),
                      ("sort", "gpa"), ("sort", "p_id\"")])
    parsed = search.parse_search_args(args)
    assert parsed.text["nationality"] == "american"
    assert parsed.sort == "gpa"


def test_empty_text_filters_are_dropped_not_rejected():
    parsed = search.parse_search_args(MultiDict([("term", ""), ("q", "")]))
    assert dict(parsed.text) == {}


def test_the_limit_is_clamped_and_the_request_is_remembered():
    parsed = search.parse_search_args(MultiDict([("limit", "500")]))
    assert (parsed.limit, parsed.requested_limit, parsed.clamped) == (100, "500", True)


def test_the_filters_are_immutable():
    parsed = search.parse_search_args(MultiDict([("term", "x")]))
    with pytest.raises(AttributeError):
        parsed.sort = "gpa"
    with pytest.raises(TypeError):
        parsed.text["term"] = "y"


def test_the_whole_contract_is_enumerable():
    assert set(search.ALLOWED_PARAMS) == {"limit", "sort", "order", "q", "term", "status",
                                          "degree", "nationality"}
    assert set(search.SORT_COLUMNS) == {"p_id", "date_added", "gpa", "gre", "gre_v", "gre_aw",
                                        "term", "status", "degree"}
    assert set(search.ORDERS) == {"asc", "desc"}


def test_the_projection_leaves_out_free_text_comments():
    assert "comments" not in search.PROJECTION
    assert set(search.SORT_COLUMNS) <= set(search.PROJECTION)


@pytest.mark.parametrize("query, message", [
    ([("debug", "1")], "unknown parameter; allowed parameters: "),
    ([("limit", "5"), ("DROP", "x")], "unknown parameter"),
    ([("sort", "gpa; DROP TABLE applicants")], "sort must be one of"),
    ([("sort", 'p_id"')], "sort must be one of"),
    ([("sort", "")], "sort must be one of"),
    ([("sort", "comments")], "sort must be one of"),
    ([("order", "desc; SELECT pg_sleep(5)")], "order must be one of"),
    ([("order", "sideways")], "order must be one of"),
    ([("limit", "abc")], "limit must be a whole number"),
    ([("limit", "1e3")], "limit must be a whole number"),
    ([("limit", "10 OR 1=1")], "limit must be a whole number"),
    ([("limit", "9" * 5000)], "limit must be a whole number"),
    ([("term", "\x00")], "term contains a control character"),
    ([("term", "A" * 10000)], "term must be at most 64 characters"),
    ([("q", "x" * 101)], "q must be at most 100 characters"),
    ([("status", "a\nb")], "status contains a control character"),
])
def test_every_rejection_is_a_400_before_any_query_exists(db_url, query, message):
    response = _client(_must_not_run, db_url).get("/api/applicants", query_string=query)
    assert response.status_code == 400
    body = response.get_json()
    assert body["ok"] is False
    assert message in body["error"]


@pytest.mark.parametrize("hostile", [
    "gpa; DROP TABLE applicants", 'p_id"', "1e3", "10 OR 1=1", "9" * 50, "x\x00y", "secret-token",
])
def test_an_error_never_echoes_the_rejected_value(db_url, hostile):
    """Some of these are valid text for term or q and legitimately reach the search; only a 400 is checked."""
    rejected = 0
    for name in ("sort", "order", "limit", "term", "q", "unexpected"):
        response = _client(lambda filters: [], db_url).get("/api/applicants",
                                                           query_string=[(name, hostile)])
        if response.status_code == 400:
            rejected += 1
            assert hostile not in response.get_json()["error"]
    assert rejected >= 3, "sort, order, and unexpected parameters must always be rejected"


def test_a_rejected_unknown_parameter_name_is_not_echoed_either(db_url):
    response = _client(_must_not_run, db_url).get("/api/applicants",
                                                  query_string=[("evil_name_xyz", "1")])
    assert response.status_code == 400
    assert "evil_name_xyz" not in response.get_json()["error"]


def test_the_error_lists_the_allowed_parameters(db_url):
    response = _client(_must_not_run, db_url).get("/api/applicants", query_string=[("debug", "1")])
    error = response.get_json()["error"]
    assert all(name in error for name in search.ALLOWED_PARAMS)


# --- the response -----------------------------------------------------------

def test_a_successful_search_reports_what_was_asked_and_what_was_used(db_url):
    seen = []

    def fake_search(filters):
        seen.append(filters)
        return [{"p_id": 1}, {"p_id": 2}]

    response = _client(fake_search, db_url).get(
        "/api/applicants", query_string=[("limit", "500"), ("sort", "gpa"), ("order", "asc")])
    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True, "limit": 100, "requested_limit": "500", "clamped": True,
        "sort": "gpa", "order": "asc", "count": 2, "rows": [{"p_id": 1}, {"p_id": 2}]}
    assert (seen[0].limit, seen[0].sort, seen[0].order) == (100, "gpa", "asc")


def test_a_search_with_no_parameters_uses_the_defaults(db_url):
    response = _client(lambda filters: [], db_url).get("/api/applicants")
    body = response.get_json()
    assert response.status_code == 200
    assert (body["limit"], body["requested_limit"], body["clamped"]) == (20, None, False)
    assert (body["sort"], body["order"], body["count"], body["rows"]) == ("date_added", "desc", 0, [])


@pytest.mark.parametrize("failure", [search.DatabaseUnavailable("down"),
                                     pytest.importorskip("psycopg").OperationalError("down")])
def test_an_unreachable_database_is_a_503_with_the_standard_message(db_url, failure):
    def failing(_filters):
        raise failure

    response = _client(failing, db_url).get("/api/applicants")
    assert response.status_code == 503
    assert response.get_json() == {"ok": False, "error": app_module.DB_UNREACHABLE}


def test_the_default_search_answers_503_when_nothing_is_listening(db_url):
    """No fake: the real make_search tries to connect, fails, and the route reports it."""
    client = create_app(Services(), database_url="postgresql+psycopg://localhost:1/unreachable",
                        testing=True).test_client()
    response = client.get("/api/applicants")
    assert response.status_code == 503
    assert response.get_json()["error"] == app_module.DB_UNREACHABLE


# --- composition ------------------------------------------------------------

def _rendered(filters):
    statement, params = search.build_search(filters)
    return statement.as_string(None), params


COLUMNS = ", ".join(f'"{name}"' for name in search.PROJECTION)


def test_builder_snapshot_without_filters():
    text, params = _rendered(_filters())
    assert text == (f'SELECT {COLUMNS} FROM "applicants" ORDER BY "date_added" DESC NULLS LAST, '
                    '"p_id" DESC LIMIT %(limit)s')
    assert params == {"limit": 20}


def test_builder_snapshot_for_a_representative_filter_set():
    filters = _filters(limit=5, sort="gpa", order="asc", text={
        "term": "Fall 2026", "nationality": "American", "q": "50%_off"})
    text, params = _rendered(filters)
    assert text == (
        f'SELECT {COLUMNS} FROM "applicants" '
        'WHERE LOWER("term") = LOWER(%(term)s) AND LOWER("us_or_international") = LOWER(%(nationality)s) '
        'AND "program" ILIKE %(q)s ESCAPE %(escape)s '
        'ORDER BY "gpa" ASC NULLS LAST, "p_id" ASC LIMIT %(limit)s')
    assert params == {"term": "Fall 2026", "nationality": "American",
                      "q": "%50\\%\\_off%", "escape": "\\", "limit": 5}


def test_values_never_appear_in_the_statement_text():
    hostile = "x' OR '1'='1"
    text, params = _rendered(_filters(text={"term": hostile, "status": hostile, "q": hostile}))
    assert hostile not in text and "'" not in text
    assert params["term"] == hostile


def test_a_hostile_identifier_forced_past_the_whitelist_renders_quoted():
    """The whitelist is the first defense; Identifier quoting is the second."""
    text, _ = _rendered(_filters(sort='gpa"; DROP TABLE x; --'))
    assert 'ORDER BY "gpa""; DROP TABLE x; --" DESC' in text
    assert sql.Identifier('gpa"; DROP TABLE x; --').as_string(None) == '"gpa""; DROP TABLE x; --"'


def test_the_direction_comes_from_the_fixed_table_not_the_request():
    for key, fragment in search.ORDERS.items():
        text, _ = _rendered(_filters(order=key))
        assert f"NULLS LAST, \"p_id\" {fragment.as_string(None)}" in text


@pytest.mark.parametrize("raw, pattern", [
    ("plain", "%plain%"), ("100%", "%100\\%%"), ("a_b", "%a\\_b%"), ("back\\slash", "%back\\\\slash%"),
    ("%", "%\\%%"), ("_", "%\\_%"), ("\\", "%\\\\%"),
])
def test_like_wildcards_in_the_query_are_escaped(raw, pattern):
    assert search._like_pattern(raw) == pattern


def test_the_statement_always_ends_in_a_bound_limit_within_the_range():
    for limit in (1, 20, 100):
        text, params = _rendered(_filters(limit=limit))
        assert text.endswith("LIMIT %(limit)s") and params["limit"] == limit


# --- execution (a stand-in cursor, no database) -----------------------------

class _Cursor:
    def __init__(self, rows):
        self.rows, self.executed = rows, []

    def execute(self, statement, params):
        self.executed.append((statement, params))

    def fetchall(self):
        return self.rows


def test_search_applicants_executes_a_composable_and_shapes_rows():
    import datetime
    row = tuple(range(len(search.PROJECTION)))
    dated = list(row)
    dated[search.PROJECTION.index("date_added")] = datetime.date(2026, 9, 12)
    cursor = _Cursor([tuple(dated)])

    rows = search.search_applicants(cursor, _filters())

    statement, params = cursor.executed[0]
    assert isinstance(statement, sql.Composable) and params == {"limit": 20}
    assert list(rows[0]) == list(search.PROJECTION)
    assert rows[0]["date_added"] == "2026-09-12"
    assert rows[0]["p_id"] == 0


def test_input_errors_share_one_base_class():
    assert issubclass(search.SearchError, InputError)
