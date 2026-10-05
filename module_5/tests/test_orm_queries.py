"""orm_queries.py: the --sql debug output, Part 6 formatting, and main().

Rubric: "Test Organization, Markers, and Coverage" (100% coverage of src/).
q1() through uq2(), dataset_summary(), and all_results() are exercised
elsewhere, since app.py's default query reads through them against a real
database (test_db_insert.py, test_integration_end_to_end.py). This file
covers what nothing else reaches: _sql()'s compiled-statement debug text,
part6_lines()'s formatting, and main(), including its --sql flag.
"""

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
