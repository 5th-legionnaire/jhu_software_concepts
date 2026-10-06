"""setup.py: packaging for the Grad Cafe analytics service.

EN 605.256 Modern Software Concepts in Python, Module 5.
Joshua Latz (jlatz1)

This file is the single source of truth for dependencies (decision D7).
requirements.txt is a fully pinned lock generated from it by
scripts/regen_lock.sh, so the two cannot drift.

The application ships as flat modules under src/ (decision D8). Those
modules import each other by bare name (``from models import ...``), and
turning them into a package would rewrite every import in the code carried
over from Module 4. The supported install is editable, ``pip install -e .``,
which resolves those imports to src/ wherever the code runs. A non-editable
``pip install .`` does not carry src/templates/ and src/static/, because flat
modules have no package to hold package data. The README states this
limitation.

Contains:
    RUNTIME:   install_requires, with the reason for each package
    DEV:       the "dev" extra (tests, linting, dependency graph, docs)
    setup():   distribution metadata
"""

from setuptools import setup

RUNTIME = [
    # Serves the analysis page, the JSON button routes, and GET /api/applicants
    # (src/app.py).
    "Flask~=3.1",
    # PostgreSQL driver (psycopg 3) for load_data.py and query_data.py, and the
    # driver SQLAlchemy uses underneath (postgresql+psycopg). Its sql module
    # provides the SQL, Identifier, and Placeholder composition Module 5 uses
    # for every statement. The [binary] extra bundles libpq, so no local
    # PostgreSQL headers or compiler are needed.
    "psycopg[binary]~=3.3",
    # ORM for models.py and orm_queries.py, and for the Flask page's database
    # reads. The assignment specifies SQLAlchemy 2.x.
    "SQLAlchemy~=2.0",
    # Loads the DB_* connection settings from .env (gitignored) instead of
    # hardcoding them. 1.2.2 or later: 1.0.1 has a symlink-following flaw when
    # it rewrites a .env file (SNYK-PYTHON-PYTHONDOTENV-16115271).
    "python-dotenv~=1.2",
    # HTML parsing for the saved result pages (clean.py), carried over from
    # Module 2. Also used by the tests to assert against the rendered page.
    "beautifulsoup4~=4.15",
    # Renders Grad Cafe pages in a real Chrome browser for Pull Data. The site
    # sits behind Cloudflare, so a plain HTTP request returns 403. No test
    # launches a browser: pull_data.py takes its driver as an injected argument.
    "selenium~=4.49",
    # HTTP client pulled in by Selenium, listed because the assignment names it.
    # 2.8.0 or later: 2.7.0 has two high-severity flaws (improper certificate
    # validation, SNYK-PYTHON-URLLIB3-20302844, and unbounded resource
    # allocation, SNYK-PYTHON-URLLIB3-20302846) and an infinite loop
    # (SNYK-PYTHON-URLLIB3-20302845), all fixed in 2.8.0.
    "urllib3~=2.8",
]

DEV = [
    # Linting: the assignment requires 10.00/10 on src/ (CI gate in ci.yml).
    "pylint~=4.1",
    # Dependency graph: pydeps renders dependency.svg from src/app.py.
    # Graphviz (the "dot" binary) is a system install, not a Python package.
    "pydeps~=3.0",
    # Test runner, marker and fixture framework.
    "pytest~=8.4",
    # Coverage plugin. pytest.ini sets --cov-fail-under=100 against src/.
    "pytest-cov~=7.0",
    # Thin wrapper over unittest.mock, for the injected scraper and loader doubles.
    "pytest-mock~=3.15",
    # Requirement and version parsing in test_packaging.py, which checks the
    # lock against the ranges declared here.
    "packaging~=26.0",
    # Parses .github/workflows/ci.yml in test_ci_config.py.
    "PyYAML~=6.0",
    # Builds docs/ into HTML, published on Read the Docs.
    "sphinx~=8.2",
    # Read the Docs theme.
    "sphinx-rtd-theme~=3.0",
]

setup(
    name="gradcafe-analytics",
    version="5.0.0",
    description="Grad Cafe admissions analytics: scraper, PostgreSQL loader, "
                "Flask analysis page.",
    author="Joshua Latz",
    python_requires=">=3.14",
    package_dir={"": "src"},
    py_modules=["app", "applicant_search", "clean", "db_safety", "load_data",
                "models", "orm_queries", "pull_data", "query_data", "scrape"],
    install_requires=RUNTIME,
    extras_require={"dev": DEV},
)
