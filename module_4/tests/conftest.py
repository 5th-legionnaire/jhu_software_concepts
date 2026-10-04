"""Shared fixtures and test doubles for the Module 4 suite.

EN 605.256 Modern Software Concepts in Python, Module 4.
Joshua Latz (jlatz1)

No test in this suite touches the live internet or runs a real scrape. The
scraper and loader reach the application only through create_app(), which
accepts them as injected callables; the fakes below stand in for them.
"""

import os
import sys

import pytest

# The application modules live in src/ and import each other flatly
# (``from models import ...``), so src/ goes on the path rather than being
# turned into a package.
SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)


# --- Test data -------------------------------------------------------------

@pytest.fixture
def fake_rows():
    """Two well-formed applicant rows with every required non-null field set."""
    # TODO: mirror the Module 3 schema exactly (p_id, program, url, status,
    # term, us_or_international, gpa, gre, gre_v, gre_aw, degree, date_added,
    # llm_generated_program, llm_generated_university, program_name, university).
    raise NotImplementedError


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
    """Truncates the applicants table before and after each db test."""
    # TODO: create_all against the test engine, TRUNCATE applicants, yield the
    # session factory, then tear down. Must leave the table empty on entry so
    # "before: target table empty" is assertable.
    raise NotImplementedError


# --- Application -----------------------------------------------------------

@pytest.fixture
def app(fake_scraper, fake_loader, db_url):
    """A testable Flask app with the scraper and loader injected."""
    # TODO: return create_app(scraper=fake_scraper, loader=fake_loader,
    #                         database_url=db_url, testing=True)
    raise NotImplementedError


@pytest.fixture
def client(app):
    """Flask test client. No browser, no manual interaction."""
    return app.test_client()
