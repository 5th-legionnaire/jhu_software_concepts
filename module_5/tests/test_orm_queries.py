"""orm_queries.py: the --sql debug output, Part 6 formatting, and main().

Rubric: "Test Organization, Markers, and Coverage" (100% coverage of src/).
q1() through uq2(), dataset_summary(), and all_results() are exercised
elsewhere, since app.py's default query reads through them against a real
database (test_db_insert.py, test_integration_end_to_end.py). This file
covers what nothing else reaches: _sql()'s compiled-statement debug text,
part6_lines()'s formatting, and main(), including its --sql flag.
"""

import ast
import re
from pathlib import Path

import pytest

import models
import orm_queries as oq
from load_data import create_connection, get_db_config, insert_records

pytestmark = pytest.mark.db


@pytest.fixture
def session_factory(clean_db, fake_rows, db_url):
    """A real ORM session factory, over a database seeded with fake_rows."""
    connection = create_connection(get_db_config(db_url))
    insert_records(connection, fake_rows)
    connection.close()
    return models.make_session_factory(db_url)


@pytest.fixture
def default_db(monkeypatch, db_url):
    """Point main()'s module-level get_session() at the test database.

    main() reads through models.get_session(), which is lru_cache'd for the
    life of the process; clearing it before and after is what keeps this
    test from leaking into whichever test happens to run next.
    """
    monkeypatch.setenv("DATABASE_URL", db_url)
    models.get_engine.cache_clear()
    models._session_factory.cache_clear()
    try:
        yield
    finally:
        models.get_engine.cache_clear()
        models._session_factory.cache_clear()


def test_sql_renders_compiled_postgres_text_with_parameters():
    """No database needed: this only compiles a statement to text."""
    text = oq._sql(oq.q1_stmt())
    assert "SELECT" in text
    assert "parameters:" in text


def test_part6_lines_formats_every_part_6_question(session_factory):
    with session_factory() as session:
        lines = oq.part6_lines(session)
    text = "\n".join(lines)
    assert "Q1  Fall 2026 applicant count: 2" in text
    assert "UQ2" in text


def test_main_prints_part6_results(monkeypatch, session_factory, default_db, capsys):
    monkeypatch.setattr("sys.argv", ["orm_queries.py"])
    oq.main()
    assert "Q1  Fall 2026 applicant count: 2" in capsys.readouterr().out


def test_main_also_prints_sql_with_the_sql_flag(monkeypatch, session_factory, default_db, capsys):
    monkeypatch.setattr("sys.argv", ["orm_queries.py", "--sql"])
    oq.main()
    output = capsys.readouterr().out
    assert "-- Q1" in output
    assert "parameters:" in output


# --- Module 5: the compiled SQL is Module 4's, plus exactly the LIMIT (CHG-16, A6.1) ---

SNAPSHOT = Path(__file__).resolve().parent / "snapshots" / "m4_orm_sql.txt"
LIMIT_CLAUSE = re.compile(r" \n LIMIT %\(param_(\d+)\)s")   # exactly how SQLAlchemy appends one


def _snapshot_blocks():
    """{builder name: (SQL text, parameters)} from the Module 4 snapshot."""
    blocks = {}
    for block in SNAPSHOT.read_text(encoding="utf-8").strip().split("\n\n"):
        header, body = block.split("\n", 1)
        text, params = body.rsplit("\nparameters: ", 1)
        blocks[header.removeprefix("-- ")] = (text, ast.literal_eval(params))
    return blocks


@pytest.mark.db
@pytest.mark.parametrize("name", sorted(_snapshot_blocks()))
def test_compiled_sql_unchanged(name):
    """Phase 3 added a LIMIT to every statement. The Module 4 SQL, captured before any change,
    must still be there word for word, followed by that one clause and nothing else.

    The snapshot is never re-captured (amendment A6.1), so this keeps showing that the
    LIMIT is the only difference, across the SQLAlchemy import change in Phase 6 as well.
    """
    old_text, old_params = _snapshot_blocks()[name]
    current = oq._sql(getattr(oq, name)())
    new_text, new_params = current.rsplit("\nparameters: ", 1)
    new_params = ast.literal_eval(new_params)

    assert new_text.startswith(old_text), "the Module 4 SQL text changed"
    suffix = new_text[len(old_text):]
    assert LIMIT_CLAUSE.fullmatch(suffix), f"more than a LIMIT was added: {suffix!r}"

    limit_name = f"param_{LIMIT_CLAUSE.fullmatch(suffix).group(1)}"
    assert limit_name not in old_params
    assert {k: v for k, v in new_params.items() if k != limit_name} == old_params
    assert 1 <= new_params[limit_name] <= 100


def test_every_module_4_statement_is_still_covered():
    """The snapshot has eleven statements, and the module still has exactly those builders."""
    builders = {n for n in dir(oq) if n.endswith("_stmt")}
    assert builders == set(_snapshot_blocks())
    assert len(builders) == 11
