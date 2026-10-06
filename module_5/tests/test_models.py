"""models.py: the Applicant model, URL building, and the default session.

Rubric: "Test Organization, Markers, and Coverage" (100% coverage of src/).
Every other test in the suite points the application at a database through
an explicit database_url, which is what make_session_factory() is for. The
module-level, lru_cache'd get_engine()/get_session() that the command-line
scripts use are never exercised that way, so this file points them at the
test database directly and clears their cache afterward.
"""

import pytest

import models

pytestmark = pytest.mark.db


def test_applicant_repr_includes_identifying_fields():
    """Pure object construction: no session, no database."""
    applicant = models.Applicant(p_id=9000001, program="Computer Science",
                                 term="Fall 2026", status="Accepted")
    text = repr(applicant)
    assert "9000001" in text
    assert "Computer Science" in text
    assert "Fall 2026" in text
    assert "Accepted" in text


# --- build_url: the DB_* variables ------------------------------------------

def test_build_url_reads_the_db_variables(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("DB_HOST", "fallback-host")
    monkeypatch.setenv("DB_PORT", "5433")
    monkeypatch.setenv("DB_NAME", "fallback-db")
    monkeypatch.setenv("DB_USER", "fallback-user")
    monkeypatch.setenv("DB_PASSWORD", "fallback-pass")

    url = models.build_url()

    assert url.drivername == "postgresql+psycopg"
    assert url.host == "fallback-host"
    assert url.port == 5433
    assert url.database == "fallback-db"
    assert url.username == "fallback-user"


# --- The default, lru_cache'd engine and session ----------------------------

@pytest.fixture
def default_db(monkeypatch, db_url):
    """Point the module-level get_engine()/get_session() at the test database.

    These are cached for the life of the process, which is correct for the
    command-line scripts but means a test must clear the cache before and
    after, or it would leak into every other test that happens to run later
    in the same session.
    """
    monkeypatch.setenv("DATABASE_URL", db_url)
    models.get_engine.cache_clear()
    models._session_factory.cache_clear()
    try:
        yield
    finally:
        models.get_engine.cache_clear()
        models._session_factory.cache_clear()


def test_get_session_connects_through_the_default_engine(clean_db, default_db):
    """A real round trip, proving get_engine()/get_session() work, not just build."""
    from sqlalchemy import func, select
    with models.get_session() as session:
        total = session.scalar(select(func.count()).select_from(models.Applicant))
    assert total == 0  # clean_db has just truncated the table


# --- _verify_mapping: the model-against-table check -------------------------

def test_verify_mapping_confirms_the_model_matches_the_table(clean_db, default_db, capsys):
    """clean_db builds the schema with load_data.create_table, the production
    path, so a match here is a genuine proof the model is still in sync."""
    models._verify_mapping()
    assert "Model matches the table." in capsys.readouterr().out


def test_verify_mapping_exits_when_the_table_does_not_match(monkeypatch, clean_db, default_db):
    """Faking the inspector avoids actually corrupting the real test schema."""
    class _FakeInspector:
        def get_columns(self, table_name):
            return [{"name": "only_this_column"}]

    monkeypatch.setattr(models, "inspect", lambda engine: _FakeInspector())

    with pytest.raises(SystemExit):
        models._verify_mapping()
