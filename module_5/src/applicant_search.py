"""applicant_search.py: the GET /api/applicants search, built and executed safely.

EN 605.256 Modern Software Concepts in Python, Module 5.
Joshua Latz (jlatz1)

New in Module 5 (CHG-08 in CHANGES.md). Until now no user input reached SQL, so
the defenses added in Phase 3 had nothing to defend. This is the smallest
surface that exercises every one of them: a read-only search over a fixed
projection, in three steps that never mix.

    parse_search_args()   validate request text into a frozen SearchFilters
    build_search()        compose the statement and its parameters, no database
    search_applicants()   execute it and shape the rows

Request text is only ever data. A sort column must be one of a fixed list and
reaches SQL through sql.Identifier; a sort direction is looked up in a table of
two fixed fragments; every filter value is a bound parameter; the limit is
clamped to 1 to 100. Nothing a client sends is spliced into SQL text, and a
rejected request never builds a statement at all.

Contains:
    Contract:    SORT_COLUMNS, ORDERS, TEXT_FILTERS, PROJECTION, ALLOWED_PARAMS
    Errors:      SearchError, DatabaseUnavailable
    Filters:     SearchFilters
    Validation:  parse_search_args()
    Composition: build_search()
    Execution:   search_applicants()
"""

from dataclasses import dataclass
from types import MappingProxyType

from psycopg import sql

from db_safety import InputError, parse_limit, validate_text

TABLE = sql.Identifier("applicants")

# Columns a client may sort by. Anything else is a 400, so this tuple is the
# whole attack surface of ORDER BY.
SORT_COLUMNS = ("p_id", "date_added", "gpa", "gre", "gre_v", "gre_aw", "term", "status", "degree")
DEFAULT_SORT = "date_added"

# Sort directions, as fixed SQL fragments. The client sends a key and never text.
ORDERS = {"asc": sql.SQL("ASC"), "desc": sql.SQL("DESC")}
DEFAULT_ORDER = "desc"

# Exact-match filters (case-insensitive): request parameter -> column, and the
# longest value accepted.
TEXT_FILTERS = {
    "term": ("term", 64),
    "status": ("status", 64),
    "degree": ("degree", 64),
    "nationality": ("us_or_international", 64),
}
QUERY_MAX_LEN = 100

# The columns returned, fixed and composed from identifiers. Free-text
# comments are left out, so the endpoint cannot be used to bulk-read them.
PROJECTION = (
    "p_id", "program", "date_added", "url", "status", "term", "us_or_international",
    "gpa", "gre", "gre_v", "gre_aw", "degree", "llm_generated_program", "llm_generated_university",
)

ALLOWED_PARAMS = ("limit", "sort", "order", "q", *TEXT_FILTERS)

# LIKE treats these as pattern characters; escaped, a client's % or _ matches
# itself instead of everything or anything.
_LIKE_SPECIALS = str.maketrans({"\\": "\\\\", "%": "\\%", "_": "\\_"})
_LIKE_ESCAPE = "\\"


class SearchError(InputError):
    """A request parameter outside the contract. The message never echoes the input."""


class DatabaseUnavailable(RuntimeError):
    """The search could not reach the database."""


@dataclass(frozen=True)
class SearchFilters:
    """A validated search request.

    Only parse_search_args() should build one from request text; build_search()
    trusts it. ``requested_limit`` is the raw text, kept so the response can
    report what was asked, and is safe to echo because it already passed the
    strict digits-only check. ``text`` holds the filters the client supplied,
    by parameter name (term, status, degree, nationality, q), as a read-only
    mapping; a filter that was absent or empty is not in it.
    """

    limit: int
    requested_limit: str | None
    clamped: bool
    sort: str
    order: str
    text: MappingProxyType


def parse_search_args(args):
    """Validate a query string into SearchFilters, or raise.

    The first value of a repeated parameter wins.

    Args:
        args: a mapping with ``get`` and ``keys``, such as Flask's request.args.

    Returns:
        SearchFilters: the validated request.

    Raises:
        SearchError: for an unknown parameter, a sort or order outside the
            contract.
        InputError: for a limit or a text value that cannot be made safe
            (LimitError is a subclass).
    """
    if any(name not in ALLOWED_PARAMS for name in args.keys()):
        raise SearchError(
            "unknown parameter; allowed parameters: " + ", ".join(sorted(ALLOWED_PARAMS)))

    requested = args.get("limit")
    limit, clamped = parse_limit(requested)

    sort = args.get("sort", DEFAULT_SORT)
    if sort not in SORT_COLUMNS:
        raise SearchError("sort must be one of: " + ", ".join(SORT_COLUMNS))
    order = args.get("order", DEFAULT_ORDER)
    if order not in ORDERS:
        raise SearchError("order must be one of: " + ", ".join(ORDERS))

    limits = {name: max_len for name, (_column, max_len) in TEXT_FILTERS.items()}
    limits["q"] = QUERY_MAX_LEN
    checked = {name: validate_text(args.get(name), name, max_len)
               for name, max_len in limits.items()}
    text = MappingProxyType({name: value for name, value in checked.items() if value is not None})
    return SearchFilters(limit=limit, requested_limit=requested, clamped=clamped,
                         sort=sort, order=order, text=text)


def _like_pattern(text):
    """A contains-pattern for ILIKE in which the client's own % and _ are literal."""
    return "%" + text.translate(_LIKE_SPECIALS) + "%"


def build_search(filters):
    """Compose the search statement and its parameters. Touches no database.

    Args:
        filters: a SearchFilters from parse_search_args().

    Returns:
        tuple[sql.Composed, dict]: the statement and its bound parameters.
    """
    conditions, params = [], {}
    for name, (column, _max_len) in TEXT_FILTERS.items():
        value = filters.text.get(name)
        if value is not None:
            conditions.append(sql.SQL("LOWER({column}) = LOWER({value})").format(
                column=sql.Identifier(column), value=sql.Placeholder(name)))
            params[name] = value
    if "q" in filters.text:
        conditions.append(sql.SQL("{column} ILIKE {pattern} ESCAPE {escape}").format(
            column=sql.Identifier("program"), pattern=sql.Placeholder("q"),
            escape=sql.Placeholder("escape")))
        params["q"] = _like_pattern(filters.text["q"])
        params["escape"] = _LIKE_ESCAPE

    where = sql.SQL(" WHERE ") + sql.SQL(" AND ").join(conditions) if conditions else sql.SQL("")
    direction = ORDERS[filters.order]
    statement = sql.SQL(
        "SELECT {columns} FROM {table}{where} ORDER BY {sort} {direction} NULLS LAST, "
        "{key} {direction} LIMIT {limit}"
    ).format(
        columns=sql.SQL(", ").join(sql.Identifier(name) for name in PROJECTION),
        table=TABLE, where=where, sort=sql.Identifier(filters.sort), direction=direction,
        key=sql.Identifier("p_id"), limit=sql.Placeholder("limit"))
    return statement, {**params, "limit": filters.limit}


def _json_value(value):
    """Dates become ISO text; everything else is already JSON-serializable."""
    return value.isoformat() if hasattr(value, "isoformat") else value


def search_applicants(cursor, filters):
    """Run the search and return its rows as dicts keyed by PROJECTION.

    Args:
        cursor: an open psycopg cursor.
        filters: a SearchFilters from parse_search_args().

    Returns:
        list[dict]: at most ``filters.limit`` rows.
    """
    statement, params = build_search(filters)
    cursor.execute(statement, params)
    return [{name: _json_value(value) for name, value in zip(PROJECTION, row)}
            for row in cursor.fetchall()]
