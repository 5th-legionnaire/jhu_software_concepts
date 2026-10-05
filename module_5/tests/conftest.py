"""Shared fixtures and test doubles for the Module 4 suite.

EN 605.256 Modern Software Concepts in Python, Module 4.
Joshua Latz (jlatz1)

No test in this suite touches the live internet, launches a browser, runs a
real scrape, or calls sleep(). The scraper, loader, and query functions reach
the application only through create_app(), which accepts them as injected
callables; the fakes below stand in for them.

Two application fixtures, for two different needs:
    app / client     fully offline: scraper, loader, and query are all
                      faked, so web, buttons, and analysis tests never touch
                      PostgreSQL.
    db_client         the scraper is still faked, but the loader and query
                      are real, against the disposable database clean_db
                      truncates before and after the test. Only db and
                      integration tests use this.
"""

import datetime
import os
import sys

import pytest

# The application modules live in src/ and import each other flatly
# (``from models import ...``), so src/ goes on the path rather than being
# turned into a package.
SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from app import create_app  # noqa: E402 (import must follow the sys.path edit above)
from load_data import create_connection, create_table, execute_query, get_db_config
from models import make_session_factory


# --- Test data -------------------------------------------------------------

@pytest.fixture
def fake_rows():
    """Two well-formed applicant rows, in the Module 2 JSON key format.

    Every required (non-null) Module 3 schema field is set, so these rows
    exercise the loader's full column mapping, not just the primary key.
    This is the shape the real scraper returns after standardization, so it
    doubles as what create_app()'s default loader expects.
    """
    return [
        {
            "url": "https://www.thegradcafe.com/result/9000001",
            "program": "Computer Science, Johns Hopkins University",
            "program_name": "Computer Science",
            "university": "Johns Hopkins University",
            "comments": "Great program, friendly faculty.",
            "date_added": "Sep 12, 2026",
            "status": "Accepted",
            "decision_date": "Sep 10",
            "term": "Fall 2026",
            "US/International": "American",
            "GRE": "GRE 165",
            "GRE V": "GRE V 160",
            "GRE AW": "GRE AW 4.5",
            "GPA": "GPA 3.80",
            "Degree": "Masters",
            "llm-generated-program": "Computer Science",
            "llm-generated-university": "Johns Hopkins University",
        },
        {
            "url": "https://www.thegradcafe.com/result/9000002",
            "program": "Electrical Engineering, Stanford University",
            "program_name": "Electrical Engineering",
            "university": "Stanford University",
            "comments": "Waitlisted first, then an offer.",
            "date_added": "Sep 13, 2026",
            "status": "Accepted",
            "decision_date": "Sep 11",
            "term": "Fall 2026",
            "US/International": "International",
            "GRE": "GRE 162",
            "GRE V": "GRE V 155",
            "GRE AW": "GRE AW 4.0",
            "GPA": "GPA 3.90",
            "Degree": "PhD",
            "llm-generated-program": "Electrical Engineering",
            "llm-generated-university": "Stanford University",
        },
    ]


@pytest.fixture
def fake_scraper(fake_rows):
    """Stands in for scrape.py: returns rows without rendering a page."""
    def _scrape(*args, **kwargs):
        return fake_rows
    return _scrape


@pytest.fixture
def failing_scraper():
    """Error-path double: raises, so the route must return non-200 and not write."""
    def _scrape(*args, **kwargs):
        raise RuntimeError("scrape failed")
    return _scrape


@pytest.fixture
def fake_loader():
    """Records what the route handed it instead of writing to PostgreSQL."""
    calls = []

    def _load(rows):
        calls.append(rows)
        return len(rows)

    _load.calls = calls
    return _load


@pytest.fixture
def fake_query():
    """Stands in for the page's database read: a fixed summary and results.

    Used by the app/client fixture, so GET /analysis and POST
    /update-analysis never reach PostgreSQL for web, buttons, or analysis
    tests. The figures exercise every formatter: a percentage that is not
    already round (33.33...%), a whole count, and non-empty grouped
    sections (uq1, uq2).
    """
    summary = {
        "total": 3,
        "first_added": datetime.date(2026, 1, 2),
        "last_added": datetime.date(2026, 9, 12),
    }
    results = {
        "q1": {"count": 3},
        "q2": {"international": 1, "classified": 3, "pct": 33.333333},
        "q3": {"avg_gpa": 3.7949, "avg_gre_q": 163.0, "avg_gre_v": 158.0, "avg_gre_aw": 4.0,
               "n_gpa": 3, "n_gre_q": 2, "n_gre_v": 2, "n_gre_aw": 1,
               "x_gpa": 0, "x_gre_q": 1, "x_gre_v": 0, "x_gre_aw": 0},
        "q4": {"avg_gpa": 3.8, "n": 2},
        "q5": {"accepted": 1, "total": 2, "pct": 50.0},
        "q6": {"avg_gpa": 3.9, "n": 1},
        "q7": {"count": 1},
        "q9": {"original": 1, "llm": 2, "difference": 1},
        "uq1": [{"group": "Reported GPA", "entries": 3, "accepted": 1, "pct": 33.333333}],
        "uq2": [{"degree": "PhD", "nationality": "American", "entries": 1,
                  "accepted": 1, "pct": 100.0}],
    }

    def _query():
        return {"summary": summary, "results": results}
    return _query


# --- Database --------------------------------------------------------------

@pytest.fixture
def db_url():
    """Test database URL; CI sets DATABASE_URL, locally fall back to a test DB."""
    return os.environ.get(
        "DATABASE_URL",
        "postgresql+psycopg://postgres:postgres@localhost:5432/gradcafe_test",
    )


@pytest.fixture
def clean_db(db_url):
    """Build the schema and truncate the applicants table before and after a test.

    Uses load_data.create_table rather than Base.metadata.create_all, so the
    schema under test is the production one: column comments and the
    ON CONFLICT (p_id) target included. Yields a session factory bound to
    the test database, for tests that read through the ORM directly.
    """
    config = get_db_config(db_url)

    def _reset():
        connection = create_connection(config)
        if connection is None:
            pytest.fail(
                f"PostgreSQL is not reachable at {db_url}. Start PostgreSQL and "
                "create the test database (see the README's Installation and "
                "setup section) before running db or integration tests.",
                pytrace=False,
            )
        try:
            create_table(connection)
            execute_query(connection, "TRUNCATE applicants")
        finally:
            connection.close()

    _reset()
    try:
        yield make_session_factory(db_url)
    finally:
        _reset()


# --- Application -----------------------------------------------------------

@pytest.fixture
def app(fake_scraper, fake_loader, fake_query, db_url):
    """A fully offline, testable Flask app: scraper, loader, and query all faked.

    testing=True selects the inline pull runner, so POST /pull-data has
    finished by the time the request returns: nothing to poll, nothing to
    sleep for. database_url is passed through even though nothing here uses
    it, so that if a fake were ever removed by mistake the app would still
    point at the disposable test database rather than a developer's real one.
    """
    return create_app(scraper=fake_scraper, loader=fake_loader, query=fake_query,
                       database_url=db_url, testing=True)


@pytest.fixture
def client(app):
    """Flask test client. No browser, no manual interaction."""
    return app.test_client()


@pytest.fixture
def db_client(fake_scraper, clean_db, db_url):
    """Flask test client backed by the real loader and query, against clean_db.

    The scraper is still faked, so no test reaches Grad Café or launches a
    browser. The loader and the page's queries are real, writing to and
    reading from the disposable database clean_db truncates before and
    after the test, which is what lets a db or integration test assert on
    actual rows. clean_db is requested (and otherwise unused here) so its
    truncation runs before this app is built.
    """
    app = create_app(scraper=fake_scraper, database_url=db_url, testing=True)
    return app.test_client()
