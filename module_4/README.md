# EN 605.256 Modern Software Concepts in Python: Module 4

**Name:** Joshua Latz
**JHED ID:** jlatz1
**Module:** Module 4, Assignment: Testing and Documentation
**Repository:** `git@github.com:5th-legionnaire/jhu_software_concepts.git`. This assignment lives under `module_4/`.
**Documentation:** _Read the Docs link pending; added when the docs are published._
**Python:** 3.14.6 (CPython, macOS)
**PostgreSQL:** 18.6 (Homebrew)

> **Note on section references.** Headings in this README are not numbered. The
> Module 3 README numbered them, and source comments referred to numbers such as
> "section 5.2"; renumbering during this module broke those references silently.
> Source comments now name headings by title instead.

## Overview

This module adds an automated test suite, continuous integration, and published
documentation to the Grad Café analytics service built in Module 3. The
application itself is unchanged in purpose: it loads scraped applicant data into
PostgreSQL, analyzes it with raw SQL and the SQLAlchemy ORM, and serves an
analysis page that can pull newly posted Grad Café entries on demand.

What is new in Module 4:

| Deliverable | Where |
| --- | --- |
| Pytest suite across five required files | `tests/` |
| Markers and the 100% coverage gate | `pytest.ini` |
| Proof of coverage | `coverage_summary.txt` |
| Continuous integration with PostgreSQL | `../.github/workflows/tests.yml` |
| Proof of a green CI run | `actions_success.png` |
| Sphinx documentation | `docs/`, published to Read the Docs |

Making the Module 3 application testable required changes to code carried over
from Modules 2 and 3. Those changes, and what forced each one, are described
under [Changes to carried-over code](#changes-to-carried-over-code).

## Repository structure

```text
module_4/
├── src/                        application code
│   ├── app.py                  Flask factory, analysis page, button routes
│   ├── pull_data.py            pull orchestration and its injection seams
│   ├── scrape.py               Grad Café page fetching (Module 2)
│   ├── clean.py                page parsing into records (Module 2)
│   ├── load_data.py            PostgreSQL connection, schema, and loader
│   ├── models.py               SQLAlchemy Applicant model and session factory
│   ├── query_data.py           raw SQL analyses and the output formatters
│   ├── orm_queries.py          the same analyses through the ORM
│   ├── templates/index.html    the analysis page
│   └── static/style.css        page styles
├── tests/                      all test code
│   ├── conftest.py             fixtures and test doubles
│   ├── test_flask_page.py      factory and page rendering
│   ├── test_buttons.py         button endpoints and busy-state gating
│   ├── test_analysis_format.py labels and percentage formatting
│   ├── test_db_insert.py       database writes, uniqueness, query contract
│   └── test_integration_end_to_end.py   pull → update → render
├── docs/                       Sphinx project
├── data/                       bulk JSON input, never imported
├── llm_hosting/                instructor-provided LLM standardizer
├── pytest.ini                  markers and the coverage gate
├── requirements.txt
├── README.md
├── coverage_summary.txt        committed terminal coverage output
└── actions_success.png         screenshot of a green CI run
```

`src/` modules import each other flatly (`from models import ...`), and
`tests/conftest.py` puts `src/` on `sys.path`. `src/` is deliberately not a
package: converting it would break parity with Module 3, where these files sat
at the top level.

## Installation and setup

### PostgreSQL

A running PostgreSQL server and a database are required. The loader creates the
table but not the database.

```bash
createuser --superuser postgres   # only if the role does not exist (Homebrew installs)
psql -d postgres -c "ALTER USER postgres PASSWORD 'choose-one';"
createdb gradcafedb
```

Homebrew's `initdb` creates a superuser named after the macOS account rather
than a `postgres` role, so on those installs the role must be created by hand.

For running the test suite, create a separate, disposable database. Tests
truncate the applicants table, so they must never point at the real one.

```bash
createdb gradcafe_test
```

### Connection settings

`DATABASE_URL` is the primary connection setting and configures both the
psycopg code and the ORM:

```bash
DATABASE_URL=postgresql+psycopg://postgres:yourpassword@localhost:5432/gradcafedb
```

The libpq variables Module 3 used (`PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`,
`PGPASSWORD`) remain as a fallback, so an existing `.env` keeps working
unchanged. `python-dotenv` populates both from a `.env` file in `module_4/` if
one exists; variables already set in the shell take precedence.

Details worth knowing:

- A URL spelled `postgresql://` has the `+psycopg` driver supplied
  automatically. A bare `postgresql://` would otherwise send SQLAlchemy looking
  for psycopg2, which this project does not install.
- User names and passwords are percent-decoded, so a password containing `@` or
  `/` is safe to carry in the URL.
- Tests override the setting through `create_app(database_url=...)` rather than
  through the environment, so a test run cannot reach the development database
  by accident.

No credentials, hosts, or machine-specific paths are hard-coded anywhere, and
`.env` is never committed.

### Python environment

One environment covers the application, the ETL code, the test suite with
coverage, and the Sphinx documentation build.

```bash
cd module_4
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

| Package | Version | Used by |
| --- | --- | --- |
| `Flask` | 3.1.3 | `app.py` |
| `psycopg[binary]` | 3.3.6 | `load_data.py`, `query_data.py`, SQLAlchemy's driver |
| `SQLAlchemy` | 2.0.54 | `models.py`, `orm_queries.py`, `app.py` |
| `python-dotenv` | 1.0.1 | connection settings |
| `beautifulsoup4`, `soupsieve` | 4.15.0, 2.9.2 | `clean.py`, and page assertions in tests |
| `selenium` | 4.49.0 | `scrape.py` |
| `urllib3` | 2.7.0 | `scrape.py` (pinned as in Module 2) |
| `pytest` | 8.4.2 | the test suite |
| `pytest-cov` | 7.0.0 | the coverage gate |
| `pytest-mock` | 3.15.1 | scraper and loader doubles |
| `sphinx`, `sphinx-rtd-theme` | 8.2.3, 3.0.2 | `docs/` |

The database driver is psycopg 3, whose PyPI package is named `psycopg`
(`psycopg2` is the previous major version). The `[binary]` extra bundles libpq,
so no PostgreSQL client headers or compiler are needed.

Local development, CI, and Read the Docs all run Python 3.14. CI pins 3.14.6
exactly; Read the Docs offers major.minor only, so it pins 3.14.

### LLM standardizer setup

The standardizer keeps its own environment, as in Module 2, because it depends
on `llama-cpp-python`, which compiles native code. Pull Data runs it in that
environment.

```bash
cd module_4/llm_hosting
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

If this environment is missing, Pull Data stops with a message saying so and
adds nothing to the database. **No test requires it**: the test suite injects a
fake scraper and never invokes the standardizer.

### Browser setup for Pull Data

Grad Café sits behind Cloudflare. As in Module 2, the verification must be
cleared once, by hand, in the persistent Chrome profile the scraper uses
(`~/.gradcafe-chrome-profile`).

**No test launches a browser.** `pull_data.py` takes its driver as an injected
argument, so the suite supplies a stand-in instead.

## How to run

All commands run from `module_4/` with the main environment active.

### The application

```bash
python3 src/app.py        # then open http://127.0.0.1:8080/analysis
```

Port 8080 rather than Flask's default 5000, which macOS's AirPlay Receiver
occupies; set `PORT` to override.

### The command-line programs

```bash
python3 src/load_data.py      # create the table and load the bulk data
python3 src/query_data.py     # raw SQL results to the console
python3 src/orm_queries.py    # SQLAlchemy results to the console
python3 src/pull_data.py      # one pull, without the web page
python3 src/models.py         # verify the model against the live table
```

`load_data.py` prints a summary on completion. Running it a second time is safe
and changes nothing:

```text
Read 30000 records: 30000 inserted, 0 already present, 0 skipped (no result id in url)
Read 30000 records: 0 inserted, 30000 already present, 0 skipped (no result id in url)
```

To inspect the table: `psql -d gradcafedb -c '\d+ applicants'` shows columns,
types, and descriptions.

### The tests

See [Testing](#testing).

## Architecture

The service has three layers. Each is described in more detail in the published
Sphinx documentation.

### Web layer

`src/app.py` exposes a `create_app()` factory. Every outward dependency arrives
as an argument, and every default is the real implementation, so running
`python3 src/app.py` is unchanged from Module 3 while a test passes fakes and
reaches no network and no database.

```python
create_app(scraper=None, loader=None, query=None, runner=None,
           database_url=None, testing=False)
```

| Argument | Shape | Real default |
| --- | --- | --- |
| `scraper` | `() -> list[dict]` | the real Grad Café pull |
| `loader` | `(records) -> int` | the real PostgreSQL loader |
| `query` | `() -> {"summary":…, "results":…}` | an ORM read |
| `runner` | `(job) -> int \| None` | a background thread, or inline when testing |

Routes and their contracts:

| Route | Method | Responses |
| --- | --- | --- |
| `/analysis` (and `/`) | `GET` | `200` the page; `503` the page with an error notice |
| `/pull-data` | `POST` | `200 {"ok": true, "inserted": n}`; `202 {"ok": true, "started": true}`; `409 {"busy": true}`; `500 {"ok": false, "error": …}` |
| `/update-analysis` | `POST` | `200 {"ok": true, "total": n}`; `409 {"busy": true}`; `503 {"ok": false, "error": …}` |

The page carries stable selectors for tests: `data-testid="pull-data-btn"` and
`data-testid="update-analysis-btn"`. Every rendered analysis value is labelled
`Answer:`, and every percentage shown as readable text is formatted to two
decimals.

### ETL layer

`scrape.py` renders Grad Café pages in Chrome and saves the HTML. `clean.py`
parses the saved pages into records. `pull_data.py` orchestrates the two,
standardizes the records with the LLM, and hands them to the loader.
`pull_data.run_pull(scraper, loader)` is the single seam the Flask route and the
tests share.

### Database layer

`load_data.py` owns the connection, the schema, and the insert. `models.py` maps
the table with the SQLAlchemy `Applicant` model and builds session factories.
`query_data.py` and `orm_queries.py` are the two read paths, answering the same
questions in raw SQL and through the ORM respectively.

## Changes to carried-over code

The Module 3 application could not satisfy this module's requirements as
written. Each change below states what the code did, what forced the change, and
what it does now. Nothing was changed for its own sake, and the Module 3 command
line behavior is preserved throughout.

### Button routes answer JSON instead of redirecting

**Before.** `pull()` and `update()` called `flash()` and returned a redirect to
the analysis page, so the browser re-rendered with a notice at the top.

**What forced it.** The assignment requires `POST /update-analysis` to return
`200` when not busy, and names the response bodies `{"ok": true}` and
`{"busy": true}` literally. A redirect returns `302`, so the Module 3 shape
could not satisfy the requirement under any test.

**Now.** Both routes answer JSON unconditionally, and the page's two buttons
call them with `fetch()`, reloading on success. Content negotiation on the
`Accept` header was considered and rejected: Flask's test client sends
`Accept: */*` by default, so the obvious `client.post("/pull-data")` would have
received a `302`. `flash()` and `session` were removed along with the
redirects; the page's status line is now rendered from the pull state, and the
rest of the information travels in the fetch response.

### Pull is no longer a subprocess

**Before.** The Pull Data route spawned `pull_data.py` with `subprocess.Popen`
and kept the process handle.

**What forced it.** A subprocess is opaque: coverage cannot see into it, and a
test cannot drive it without actually launching one. The assignment forbids
tests that depend on long-running scrapes.

**Now.** `pull_data.run_pull(scraper, loader)` is an in-process callable. The
browser, the LLM standardizer, the database connection, and even the politeness
delay between page requests all arrive as arguments, so each can be replaced in
a test. The real application still does not block: `create_app` takes a
`runner`, which defaults to a daemon thread outside tests and to inline
execution inside them. That separation is deliberate. _How_ a pull executes and
_what_ it does are different concerns, and conflating them is what made the
Module 3 version untestable.

### Busy state is observable

**Before.** Busy was inferred from `process.poll()` on the subprocess handle.

**What forced it.** The assignment forbids `sleep()` for busy-state checks and
requires state to be observable or injectable. Polling a subprocess is neither.

**Now.** `app.config["PULL_STATE"]` holds a small `PullState` object with a
plain `busy` flag and a `last` status dictionary. A test sets `state.busy = True`
and posts. No test in the suite calls `sleep()`.

### Update Analysis is gated during a pull

**Before.** Update Analysis refreshed during a pull and said so in its notice.
The Module 3 docstring argued that this was safe, and it was right: the loader
commits a pull in a single transaction, so a concurrent read sees the database
either entirely before the new entries or entirely after them, never halfway.

**What forced it.** The assignment requires `POST /update-analysis` to return
`409` with `{"busy": true}` and perform no update while a pull is in progress.

**Now.** The route is gated. This is a reporting choice rather than a
correctness fix: the Module 3 reasoning about transaction isolation still
holds, but a refresh taken mid-pull reports a total that is about to change, so
the pull now has the page to itself and the figure shown is never
half-superseded.

### `DATABASE_URL` replaces the `PG*` variables as the primary setting

**Before.** `get_db_config()` read five `PG*` variables with `os.environ[...]`,
and `models.get_engine()` was `lru_cache`d on them.

**What forced it.** The assignment requires `DATABASE_URL` and requires tests to
be able to override the configuration. A cached, process-wide engine cannot be
redirected by a factory argument.

**Now.** `load_data.get_db_config(database_url=None)` and
`models.build_url(database_url=None)` mirror each other: explicit argument
first, then `DATABASE_URL`, then the `PG*` fallbacks.
`models.make_session_factory()` is deliberately uncached, so two callers asking
for different URLs get factories reaching different databases. The `lru_cache`d
`get_engine()` and `get_session()` remain for the command-line programs, which
keeps Module 3 behavior intact.

### The loader can insert records held in memory

**Before.** `load_data(connection, path)` read a JSON file and inserted its
contents, which was the only way to insert anything.

**What forced it.** An in-process pull has records in memory, not in a file.

**Now.** `insert_records(connection, records)` holds the transaction, and
`load_data(connection, path)` is a thin file-reading wrapper over it. The
Module 3 call signature and behavior are unchanged. Separately,
`pull_data.load_records` now calls `create_table` first, so a pull against a
fresh database no longer requires `load_data.py` to have been run; it is
`CREATE TABLE IF NOT EXISTS`, so it remains a no-op otherwise.

### Page markup gained test selectors and consistent formatting

**Before.** The buttons sat inside `<form>` elements with no stable selectors.
Answers rendered as a label and a value with no `Answer:` text. Sample-size
shares were rounded to one decimal and printed into an `aria-label`
("1.3% of the dataset"), and the thin-sample threshold printed as a bare `5%`.

**What forced it.** The assignment requires stable selectors, requires at least
one `Answer:` label, and forbids rendering percentages with varying precision.
Both the `aria-label` and the legend are readable page text, so both were in
scope.

**Now.** Both buttons carry `data-testid` attributes. Every answer is prefixed
with an `Answer:` label. Every percentage rendered as text goes through
`fmt_pct` and shows two decimals. CSS bar widths keep their numeric share, as
they are geometry rather than analysis output.

### Path constants and docstrings were repaired after the move into `src/`

Copying `module_3/` to `module_4/src/` left four path constants resolving under
`src/` and pointing at locations that no longer existed:
`load_data.DEFAULT_DATA_FILE`, `pull_data.WORK_DIR`, `pull_data.LLM_DIR`, and
`app.PULL_LOG`. They now resolve from `module_4/`, and `app.PULL_LOG` is gone
with the subprocess. Every module's `Usage:` block was likewise stale
(`python3 load_data.py`) and now reads `python3 src/load_data.py`, run from
`module_4/`.

Docstring attribution headers now read Module 4 with a one-line note of where
each file originated. References that name an earlier module's _artifact_ were
left alone, because they are accurate: "one Module 2 record (its JSON keys)"
and "directly from the Module 3 assignment schema" describe a real data format
and a real source, and rewriting them would turn correct history into a false
claim.

## Data schema

### Required columns

The table implements the Module 3 assignment schema exactly. Each column's
description is stored in the database catalog via `COMMENT ON COLUMN`, so it is
visible to anyone inspecting the table rather than living only in source code.

| Column | Type | Description |
| --- | --- | --- |
| `p_id` | integer | Unique identifier |
| `program` | text | University and Department/Program |
| `comments` | text | Applicant comments |
| `date_added` | date | Date entry was added |
| `url` | text | Link to Grad Café entry |
| `status` | text | Admission status |
| `term` | text | Intended start term |
| `us_or_international` | text | Applicant nationality classification |
| `gpa` | float | Applicant GPA |
| `gre` | float | GRE Quantitative score |
| `gre_v` | float | GRE Verbal score |
| `gre_aw` | float | GRE Analytical Writing score |
| `degree` | text | Degree type |
| `llm_generated_program` | text | LLM-generated department/program |
| `llm_generated_university` | text | LLM-generated university |

### Uniqueness policy

`p_id` is the primary key and `url` additionally carries a `UNIQUE` constraint.
`p_id` is the Grad Café result id parsed out of the entry URL, not a generated
sequence, so the two constraints agree by construction.

Inserts use `ON CONFLICT (p_id) DO NOTHING`. Pulling overlapping data is
therefore a no-op for rows already present rather than an error or a duplicate,
which is what makes a repeated pull safe. `insert_records` reports the split:
how many were inserted, how many were already present, and how many were skipped
for having no result id.

### Additional columns

Three further columns are appended after the required ones. They are not part of
the assignment schema, and their descriptions are my own.

| Column | Type | Description |
| --- | --- | --- |
| `program_name` | text | Program name alone, as presented by the site |
| `university` | text | University name alone, as presented by the site |
| `decision_date` | text | Date the decision was given, as presented by the site (no year) |

They are included so that no field parsed in Module 2 is dropped on the way into
the database. The Module 2 requirement to preserve applicant-provided data
carries forward: a loader that silently discarded three of the seventeen parsed
fields would undo that.

`university` matters most. Module 2 measured the LLM standardizer's
`llm-generated-university` against the site's own university text and found
roughly 550 records, about 1.8%, where the model substituted a different
institution: `University of Michigan` became `University of Milan` in 287
records. That bears directly on the question comparing the original fields
against the LLM fields.

Appending the extra columns after the required ones, rather than interleaving
them, keeps the required schema recognizable in order. They are mapped in the
`Applicant` model as well, so the model reflects the table as it actually exists.

## Analysis rules

### Validity ranges

Every numeric column was audited against the scale it is supposed to be on
before any averaging query was written. The `gre` column is mostly not
quantitative scores: Grad Café labels the field only `GRE`, and 1,406 applicants
entered a combined score on the 260 to 340 scale against 954 who entered a
quantitative score on the 130 to 170 scale. A plain `AVG(gre)` would mix the two
and describe no one.

Averages therefore include only values on the metric's own scale:

| Metric | Valid range | Included | Excluded |
| --- | --- | --- | --- |
| `gpa` | 0 to 4.0 | 17,974 | 134 |
| `gre` (quantitative) | 130 to 170 | 954 | 1,438 |
| `gre_v` | 130 to 170 | 2,002 | 4 |
| `gre_aw` | 0 to 6 | 1,807 | 80 |

The rationale is the assignment's own averaging rule: an applicant contributes
to an average only if they provide that metric, and a value off the metric's
scale does not provide it in any usable sense. The ranges are applied inside the
queries only. The table holds every value as reported, consistent with the
Module 2 rule against altering source data, and the exclusion counts are
reported alongside each average on the page.

The ranges are defined once as constants in `query_data.py` and imported by
`orm_queries.py`, so the raw SQL and ORM answers apply identical filters.

### Data window caveat

The dataset covers entries _added_ between 1 January and 14 September 2026. That
window captures most of the Fall 2026 cycle but only the tail of Fall 2025,
whose decisions were largely posted in early 2025. The Fall 2025 acceptance rate
is therefore computed over a small subset of late posters, which is not a random
sample: 29,576 Fall 2026 entries against 192 for Fall 2025. The denominator is
reported alongside the percentage, and the page's sample-size bar turns amber
below 5.00% of the dataset so thin evidence reads as thin.

## Testing

_This section is completed as the suite lands. See `PLAN.md` for the current
phase._

The full suite runs from `module_4/`, because `pytest.ini` scopes coverage to
`src/` relative to itself:

```bash
cd module_4
pytest -m "web or buttons or analysis or db or integration"
```

Every test carries at least one marker; unmarked tests are not permitted.

| Marker | Covers |
| --- | --- |
| `web` | Flask route and page-structure tests |
| `buttons` | Pull Data and Update Analysis endpoints, and busy-state gating |
| `analysis` | Label and percentage formatting |
| `db` | Schema, inserts, selects, uniqueness |
| `integration` | End-to-end pull → update → render |

Tests reach the application only through `create_app()`. No test touches the
live internet, launches a browser, runs a real scrape, or calls `sleep()`. The
`web` and `analysis` tests inject a fake `query` and need no database at all;
only the `db` and `integration` markers require PostgreSQL.

_Pending: the fixture and test-double reference, the coverage figure, and the
contents of `coverage_summary.txt`._

## Documentation

_Pending: the published Read the Docs URL._

The Sphinx project lives in `docs/`. To build it locally:

```bash
cd module_4
sphinx-build -b html docs docs/_build/html
```

It covers overview and setup, architecture, an autodoc API reference for every
module in `src/`, a testing guide, and operational notes.

## Known issues

1. **`gre` holds mixed scales.** The assignment describes `gre` as the GRE
   Quantitative score, but the site's `GRE` field holds combined scores for most
   applicants who report one. Averages use only on-scale values; see
   [Validity ranges](#validity-ranges).
2. **LLM standardizer defects carry through.** The acronym-casing and
   confabulation defects documented in Module 2 are present in
   `llm_generated_university` and are loaded as generated.
3. **Decision dates have no year.** The site presents them without one, so
   `decision_date` is stored as text rather than a date.
4. **Fall 2025 coverage is partial.** See
   [Data window caveat](#data-window-caveat).
5. **A pull started from the web page does not survive a restart.** Busy state
   lives in the application process. Restarting the server mid-pull forgets the
   running pull, as it did in Module 3.
