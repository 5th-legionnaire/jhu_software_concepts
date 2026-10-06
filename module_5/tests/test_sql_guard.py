"""The SQL guard: no SQL built from strings, only composed SQL executed, every SELECT limited.

EN 605.256 Modern Software Concepts in Python, Module 5.
Joshua Latz (jlatz1)

Three rules, each checked two ways. The static check walks the source of
src/*.py and fails on any f-string, string concatenation, % formatting, or
str.format whose literal text holds SQL, reporting file:line. The runtime
checks wrap a real cursor in a spy that records the type of every statement
the code hands to the driver, and capture every statement the ORM sends.

A guard that never fails proves nothing, so each check is also run against
code written to violate it, and must report that code.
"""

import ast
import re
from pathlib import Path

import pytest
from psycopg import sql
from sqlalchemy import event
from sqlalchemy.dialects import postgresql
from werkzeug.datastructures import MultiDict

import applicant_search
import db_safety
import load_data as ld
import models
import orm_queries as oq
import pull_data
import query_data as qd
from spies import SpyConnection, SpyCursor

pytestmark = pytest.mark.security

SRC = Path(__file__).resolve().parent.parent / "src"

# Capitalized, as SQL is written in this project. Lower-case prose such as
# "select a degree" or "from the database" is not SQL and must not be flagged.
SQL_WORDS = re.compile(r"\b(SELECT|INSERT|UPDATE|DELETE|CREATE|ALTER|DROP|FROM|WHERE|LIMIT)\b")


# --- the static guard -------------------------------------------------------

def _is_sql_literal(node):
    """True for a call to psycopg's sql.SQL(...) or SQL(...)."""
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    return (isinstance(func, ast.Attribute) and func.attr == "SQL") or \
           (isinstance(func, ast.Name) and func.id == "SQL")


def _str_constants(node):
    """The text of string Constants that are direct children of the node's own expression."""
    return [child.value for child in ast.iter_child_nodes(node)
            if isinstance(child, ast.Constant) and isinstance(child.value, str)]


def find_sql_string_building(source, filename="<source>"):
    """Return 'file:line: what' for every place SQL text is built from strings.

    Flags an f-string, a ``+`` or ``%`` with a string-literal operand, and
    ``.format()`` on a string literal, when the literal text matches SQL_WORDS.
    ``.format()`` on a ``sql.SQL(...)`` literal is psycopg's composition API,
    which quotes what it inserts, so it is allowed.
    """
    findings = []
    for node in ast.walk(ast.parse(source)):
        where = f"{filename}:{node.lineno}" if hasattr(node, "lineno") else filename
        if isinstance(node, ast.JoinedStr):
            if SQL_WORDS.search(" ".join(_str_constants(node))):
                findings.append(f"{where}: SQL in an f-string")
        elif isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Mod)):
            if SQL_WORDS.search(" ".join(_str_constants(node))):
                findings.append(f"{where}: SQL joined with a string operator")
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr == "format" and not _is_sql_literal(node.func.value):
            receiver = node.func.value
            if isinstance(receiver, ast.Constant) and isinstance(receiver.value, str) \
                    and SQL_WORDS.search(receiver.value):
                findings.append(f"{where}: SQL passed to str.format")
    return findings


def test_no_sql_string_building():
    findings = []
    for path in sorted(SRC.glob("*.py")):
        findings += find_sql_string_building(path.read_text(encoding="utf-8"), path.name)
    assert findings == []


@pytest.mark.parametrize("source, expected", [
    ('q = f"SELECT * FROM t WHERE a = {x}"', "SQL in an f-string"),
    ('q = "SELECT * FROM t WHERE a = " + x', "SQL joined with a string operator"),
    ('q = x + " WHERE a = 1"', "SQL joined with a string operator"),
    ('q = "SELECT * FROM t WHERE a = %s" % x', "SQL joined with a string operator"),
    ('q = "SELECT * FROM t WHERE a = {}".format(x)', "SQL passed to str.format"),
    ('q = "DROP TABLE t; --" + name', "SQL joined with a string operator"),
])
def test_guard_reports_sql_built_from_strings(source, expected):
    findings = find_sql_string_building(source, "bad.py")
    assert len(findings) == 1
    assert findings[0].startswith("bad.py:1:") and expected in findings[0]


@pytest.mark.parametrize("source", [
    'q = sql.SQL("SELECT {} FROM t").format(sql.Identifier("a"))',     # psycopg composition
    'q = sql.SQL("SELECT ") + sql.SQL("1")',                            # composables joined
    'q = SQL("SELECT {c}").format(c=Identifier("a"))',
    'msg = f"Read {n} records, {m} inserted"',                          # no SQL in it
    'msg = "select a degree from the list"',                            # lower-case prose
    'msg = "Added " + str(n) + " entries"',
    'msg = "{} of {}".format(a, b)',
])
def test_guard_accepts_composition_and_ordinary_strings(source):
    assert find_sql_string_building(source) == []


# --- the runtime guard: what reaches the driver -----------------------------

def non_composable(seen):
    """The recorded statements that are not psycopg Composables."""
    return [type(statement).__name__ for statement in seen
            if not isinstance(statement, sql.Composable)]


@pytest.fixture
def spy_connection(clean_db, db_url):
    """A real connection as the runtime role, wrapped in a spy, and its record."""
    connection = ld.create_connection(ld.get_db_config(db_url))
    seen = []
    yield SpyConnection(connection, seen), seen
    connection.close()


@pytest.fixture
def spy_owner_connection(clean_db, admin_url):
    """The same, as the owner role, for the statements only the owner may run (DDL)."""
    connection = ld.create_connection(ld.get_db_config(admin_url))
    seen = []
    yield SpyConnection(connection, seen), seen
    connection.close()


def test_spy_reports_a_bare_string():
    """The spy must be able to catch what it exists to catch."""
    seen = []
    cursor = SpyCursor(_Recorder(), seen)
    cursor.execute("SELECT 1")
    cursor.executemany("SELECT 2", [])
    cursor.execute(sql.SQL("SELECT 3"))
    assert non_composable(seen) == ["str", "str"]


class _Recorder:
    """A cursor stand-in that accepts anything."""

    def execute(self, *_args, **_kwargs):
        return None

    executemany = execute


@pytest.mark.db
def test_every_execute_receives_composable(spy_connection, fake_rows):
    connection, seen = spy_connection

    ld.insert_records(connection, fake_rows)
    inserts = len(seen)
    with connection.cursor() as cursor:
        qd.run_all(cursor)

    assert inserts >= 2, "insert_records should have executed a count and an insert"
    assert len(seen) - inserts == 11, "run_all runs q1 to q9, uq1, and uq2"
    assert non_composable(seen) == []


@pytest.mark.db
def test_search_applicants_executes_a_composable(spy_connection):
    """The search endpoint's statement is composed too, with hostile values among its filters."""
    connection, seen = spy_connection
    filters = applicant_search.parse_search_args(
        MultiDict([("term", "' OR '1'='1"), ("q", "100%"), ("sort", "gpa")]))
    with connection.cursor() as cursor:
        applicant_search.search_applicants(cursor, filters)
    assert len(seen) == 1 and non_composable(seen) == []


@pytest.mark.db
def test_create_table_and_count_receive_composables(spy_owner_connection):
    connection, seen = spy_owner_connection
    ld.create_table(connection)
    ld._count_rows(connection)
    assert seen and non_composable(seen) == []


# --- the LIMIT guard --------------------------------------------------------

@pytest.mark.parametrize("name", sorted(qd.QUESTIONS))
def test_every_select_has_limit(name):
    """Every analysis statement ends in a bound LIMIT inside the permitted range."""
    statement, params = qd.QUESTIONS[name]()
    text = statement.as_string(None)
    assert text.endswith("LIMIT %(limit)s")
    assert len(re.findall(r"\bLIMIT\b", text)) == 1
    assert db_safety.MIN_LIMIT <= params["limit"] <= db_safety.MAX_LIMIT


def test_the_search_statement_has_a_bound_limit_in_the_permitted_range():
    """Whatever the request, the search ends in LIMIT %(limit)s with a value from 1 to 100."""
    for query in ([], [("limit", "1000000")], [("limit", "-5")], [("q", "x"), ("term", "y")]):
        filters = applicant_search.parse_search_args(MultiDict(query))
        statement, params = applicant_search.build_search(filters)
        assert statement.as_string(None).endswith("LIMIT %(limit)s")
        assert db_safety.MIN_LIMIT <= params["limit"] <= db_safety.MAX_LIMIT


def test_every_question_is_covered_by_the_limit_check():
    assert sorted(qd.QUESTIONS) == ["q1", "q2", "q3", "q4", "q5", "q6", "q7", "q8", "q9", "uq1", "uq2"]


def test_single_row_aggregates_are_limited_to_one_and_grouped_ones_to_the_maximum():
    limits = {name: build()[1]["limit"] for name, build in qd.QUESTIONS.items()}
    assert limits["uq1"] == limits["uq2"] == db_safety.MAX_LIMIT
    assert {limits[name] for name in qd.QUESTIONS if not name.startswith("uq")} == {1}


@pytest.mark.parametrize("builder", sorted(n for n in dir(oq) if n.endswith("_stmt")))
def test_every_orm_statement_builder_is_limited(builder):
    statement = getattr(oq, builder)()
    compiled = str(statement.compile(dialect=postgresql.dialect()))
    assert " LIMIT " in compiled
    assert db_safety.MIN_LIMIT <= statement._limit <= db_safety.MAX_LIMIT


def test_the_orm_builder_check_would_catch_an_unlimited_statement():
    unlimited = oq.q1_stmt().limit(None)
    assert " LIMIT " not in str(unlimited.compile(dialect=postgresql.dialect()))


@pytest.fixture
def orm_statements(clean_db, fake_rows, db_url):
    """Every SQL statement SQLAlchemy sends while a test runs, and a seeded factory."""
    connection = ld.create_connection(ld.get_db_config(db_url))
    ld.insert_records(connection, fake_rows)
    connection.close()
    factory = models.make_session_factory(db_url)
    sent = []
    engine = factory.kw["bind"]
    event.listen(engine, "before_cursor_execute",
                 lambda conn, cursor, statement, *rest: sent.append(statement))
    return factory, sent


def _selects(sent):
    """The SELECTs the application sent. SQLAlchemy's own pg_catalog lookups are not ours."""
    return [statement for statement in sent
            if statement.lstrip().upper().startswith("SELECT") and "pg_catalog" not in statement]


@pytest.mark.db
def test_every_select_the_orm_executes_has_limit(orm_statements):
    """Runtime proof, beyond the builders: fetch_one, the summary, and the pull's read too."""
    factory, sent = orm_statements
    with factory() as session:
        oq.all_results(session)
        oq.fetch_one(session)
        oq.dataset_summary(session)
    pull_data._newest_in_database(factory)

    selects = _selects(sent)
    assert len(selects) >= 13
    assert [s for s in selects if " LIMIT " not in s] == []


@pytest.mark.db
def test_the_model_check_select_has_limit(orm_statements, monkeypatch, capsys):
    factory, sent = orm_statements
    monkeypatch.setattr(models, "get_engine", lambda: factory.kw["bind"])
    monkeypatch.setattr(models, "get_session", factory)
    models._verify_mapping()
    capsys.readouterr()
    selects = _selects(sent)
    assert len(selects) == 2
    assert [s for s in selects if " LIMIT " not in s] == []
