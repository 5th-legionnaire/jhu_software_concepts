# Module 4 execution plan

EN 605.256, Module 4: Pytest and Sphinx. 100 points. Source of truth is
`assignment/Module 4 - Testing and Documentation Assignment.pdf`.

## Phase 0: refactor contract (COMPLETE)

The Module 3 app could not satisfy the rubric as written. What was built, and
the three places this plan was amended along the way.

### The injection seam

```python
create_app(scraper=None, loader=None, query=None, runner=None,
           database_url=None, testing=False)
```

Every argument defaults to the real implementation, so `python3 src/app.py` is
unchanged. The callables:

| Argument | Shape | Real default |
|----|----|----|
| `scraper` | `() -> list[dict]` | `pull_data.scrape_new_records` |
| `loader` | `(records) -> int` | `pull_data.load_records` |
| `query` | `() -> {"summary":…, "results":…}` | ORM read via `make_query` |
| `runner` | `(job) -> int \| None` | `run_in_background`, or `run_inline` when testing |

**Amendment 1: `runner` was added.** This plan previously asked for an
in-process `run_pull` *and* for the subprocess to stay as the default injected
behavior. Those contradict: a subprocess returns an exit code, not rows, so the
route cannot thread scraper to loader through it. Splitting *how* a pull
executes (`runner`) from *what* it does (`scraper`, `loader`) satisfies both
intents. The real app gets a daemon thread, so a multi-minute pull still does
not block the page; tests get `run_inline`, so a `POST /pull-data` has finished
pulling by the time it returns and there is nothing to wait on.

**Amendment 2: `query` injection is load-bearing, not a nicety.** Because the
page's entire database read is one injected callable, `test_flask_page.py` and
`test_analysis_format.py` run with **no PostgreSQL at all**. Only the `db` and
`integration` markers need a database, which is what keeps CI's Postgres
service off the critical path for 7 of the 20 tests.

### The JSON contract

Chosen: **always JSON**, with the page's two buttons calling the routes via
`fetch()` and reloading on success. Content negotiation on `Accept` was
rejected because Flask's test client sends `Accept: */*` by default, so the
obvious `client.post("/pull-data")` would have received a 302.

```
POST /pull-data        200 {"ok": true, "inserted": n}    finished in-request
                       202 {"ok": true, "started": true}  running in background
                       409 {"busy": true}                 a pull is already running
                       500 {"ok": false, "error": text}   stopped, nothing written
POST /update-analysis  200 {"ok": true, "total": n}
                       409 {"busy": true}
                       503 {"ok": false, "error": text}   database unreachable
GET  /analysis         200 the page   (GET / is an alias on the same view)
                       503 the page, rendered with an error notice
```

`flash()` and `session` are gone with the redirects. The page's status line now
comes from `PullState.last`, server-rendered, and from the fetch response.

### Observable busy state

`app.config["PULL_STATE"]` holds a `PullState` with a plain `busy` bool and a
`last` status dict. A test sets `state.busy = True` and posts. Module 3
inferred busy from `subprocess.poll()`, which no test could drive without a
real subprocess to wait on. `pull_data._scrape_new_pages` also takes its
politeness delay as a `sleep` argument, so no test anywhere needs `sleep()`.

Update Analysis is now **gated** during a pull, per the rubric. Module 3 allowed
it. Note in `docs/operations.rst` that the gate is a reporting choice, not a
correctness one: the loader's single transaction already made a concurrent read
safe, but a refresh taken mid-pull reports a total that is about to change.

### Configuration

`DATABASE_URL` is primary, with the `PG*` variables as fallback, in two places
that now mirror each other:

- `load_data.get_db_config(database_url=None)` -> psycopg kwargs
- `models.build_url(database_url=None)` -> SQLAlchemy URL

A URL spelled `postgresql://` gets the `+psycopg` driver supplied; one that
names a driver keeps it. User names and passwords are percent-decoded, so a
password containing `@` is safe in the URL. `models.make_session_factory(url)`
is uncached and is what lets `create_app(database_url=...)` redirect the whole
application; the `lru_cache`d `get_engine`/`get_session` stay for the CLI
scripts, preserving Module 3 behavior.

### Template

- `data-testid="pull-data-btn"` and `data-testid="update-analysis-btn"`.
- Every answer carries an `Answer:` label, as
  `<span class="answer-label">Answer:</span>` prefixing the value. 16 on a
  full page.
- `<title>` and `<h1>` both contain `Analysis`.
- **Amendment 3: the two-decimal rule had to reach further than the values.**
  `_with_shares` computed `share_pct` to one decimal and the template printed
  it into an `aria-label` ("1.3% of the dataset"), and `thin_pct` printed as a
  bare `5%`. Both are readable page text, so both violated the SHALL NOT on
  varying precision. Rows now also carry `share_text`, and the page gets
  `thin_pct_text`, each through `fmt_pct`. CSS bar widths keep the numeric
  `share_pct`: they are geometry, not analysis output.

### Also fixed in phase 0, not in the original plan

- **The `module_4/.venv` was broken.** Its `pyvenv.cfg` still named `module_3`,
  so `pip install` wrote into module_3's `site-packages`, and it had no
  `pytest`, `pytest-cov`, `pytest-mock`, or `sphinx`. Recreated on 3.14.6
  against `requirements.txt`.
- **The module_3 to `src/` move broke four path constants**, all of which
  resolved under `src/` and pointed at nothing:
  `load_data.DEFAULT_DATA_FILE`, `pull_data.WORK_DIR`, `pull_data.LLM_DIR`, and
  `app.PULL_LOG`. They now resolve from `module_4/` via a `PROJECT_DIR`
  constant. `app.PULL_LOG` is gone entirely with the subprocess.
- **`load_data.load_data()` was split**, so a pull can insert rows already in
  memory: `insert_records(connection, records)` holds the transaction, and
  `load_data(connection, path)` is now a thin file-reading wrapper over it.
  Module 3's call signature is unchanged.
- **`pull_data.load_records` calls `create_table` first**, so a pull against a
  fresh database no longer requires `load_data.py` to have been run. It is
  `CREATE TABLE IF NOT EXISTS`, so it stays a no-op in every other case.
- `PullError` carries the "stopped, nothing written" messages that Module 3
  returned as exit codes, so the route can put the reason in its 500 body.

## Phase 1: tests (COMPLETE)

All 20 tests across the five required files pass:
`pytest -m "web or buttons or analysis or db or integration"` → `20 passed`.

### Two application fixtures, not one

The stubbed `conftest.py` had a single `app` fixture, built from
`fake_scraper` and `fake_loader`. That cannot serve both halves of the suite:
web, buttons, and analysis tests need zero PostgreSQL, but db and
integration tests need rows to actually land and actually be queryable.
Faking the loader rules out the first; using the real loader rules out the
second, for the *same* fixture.

Resolved with two fixtures:

| Fixture | scraper | loader | query | Used by |
|---|---|---|---|---|
| `app` / `client` | `fake_scraper` | `fake_loader` (records calls, writes nothing) | `fake_query` (new) | `web`, `buttons`, `analysis` |
| `db_client` | `fake_scraper` | real, against `clean_db` | real, against `clean_db` | `db`, `integration` |

Adding `fake_query` is what makes `buttons` tests database-free too, not
only `web` and `analysis` as originally scoped: `POST /update-analysis` calls
`query()` even when not busy, so without a fake it would reach PostgreSQL.
Measured: the 13 `web`/`buttons`/`analysis` tests run in 0.04s with no
`DATABASE_URL` set at all, confirming they touch no database.

`app` still passes `testing=True`, selecting the inline pull runner so a
`POST /pull-data` has finished by the time the request returns.

`clean_db` builds the schema with `load_data.create_table` (not
`Base.metadata.create_all`), so column comments and the `ON CONFLICT (p_id)`
target are the production ones. If PostgreSQL is unreachable, it calls
`pytest.fail()` with a message naming what to do, rather than skipping: a
silent skip would quietly reduce coverage while looking like a neutral
result.

### A query function the suite needed and the app did not have

The assignment's database-writes section asks for "a simple query function"
returning "a dict with our expected keys (the required data fields within
M3)" — distinct from `orm_queries.all_results()`, which returns the nested
per-question shape the analysis page consumes. No such function existed.
Added to `orm_queries.py`:

- `REQUIRED_FIELDS`: the 15 Module 3 schema columns, in schema order.
  Excludes `program_name`, `university`, `decision_date` (the
  README's "Additional columns").
- `applicant_dict(applicant)`: one `Applicant` row as a dict of those fields.
- `fetch_one(session)`: the newest-by-`p_id` row, same shape, or `None`.

### Test data

`fake_rows` (two records, Module 2 JSON key format) is deliberately the
shape the real scraper returns after standardization, so the same fixture
exercises `create_app()`'s default loader path end to end in `db_client`
tests, not just the fake path.

### A bug this phase's smoke-testing surfaced, not fixed here

Constructing a `DATABASE_URL` by hand with an unescaped `@` in the password
fails to connect (psycopg reads past the `@` as the host separator). This is
expected `urllib.parse` behavior, not a code defect: `models.build_url()`
already percent-decodes a URL that was percent-*encoded* going in. Noted
here because it cost real debugging time once; a password containing `@`,
`/`, or `:` must be percent-encoded by whoever writes the `.env` or exports
`DATABASE_URL`.

## Phase 2: coverage to 100 (COMPLETE)

```
TOTAL  802  0  100%
Required test coverage of 100% reached. Total coverage: 100.00%
102 passed in 0.79s
```

Committed to `module_4/coverage_summary.txt`, produced by
`pytest -m "web or buttons or analysis or db or integration"` exactly as the
README documents running it.

Worked `term-missing` top down, file by file, after `test_pull_pipeline.py`
(below) closed the scraper gap: `query_data.py` (51% -> 100%), `scrape.py`
(39% -> 100%), `load_data.py` (74% -> 100%), `models.py` (70% -> 100%),
`orm_queries.py` (86% -> 100%), `clean.py` (83% -> 100%), `pull_data.py`
(87% -> 100%), `app.py` (91% -> 100%). Four new test files:
`test_scrape.py`, `test_query_data.py`, `test_load_data.py`,
`test_orm_queries.py`, `test_models.py`; the rest extended existing files.

### check_llm.py, run_llm.sh, llm_hosting/

Deliberately outside `src/`, so they do not count toward `--cov=src`. Left
there.

### query_data.py: a real, unused code path, tested for real

`app.py` reads results through `orm_queries.py` (the ORM path); nothing calls
`query_data.py`'s raw-SQL `q1()` through `uq2()`, `run_all()`, `main()`. A
fake cursor would have closed the coverage gap cheaper, but would only prove
Python unpacks a canned tuple, not that the SQL text is still valid Postgres.
`test_query_data.py` runs every question against the real test database
instead, which is a stronger test for the same cost and fits the `db` marker
exactly ("database schema/inserts/selects").

### scrape.py: the same reasoning as pull_data.py, one layer down

`scrape_data()`, the Module 2 one-time historical-pull function flagged as a
coverage gap when Phase 2 began, calls `_start_browser()` directly with no
injection point, the same problem `pull_data.py` had before Phase 0/1.
Fixed the same way: added `browser_factory`, `fetch_html`, and `sleep`
parameters, defaulting to the real implementations, letting
`test_scrape.py` drive the real stop-on-no-page / stop-on-no-entries /
stop-at-max-entries / resume-a-previous-run logic with fakes.
`_fetch_html()`'s `TimeoutException` branch is the one place left genuinely
untestable without either a real browser timeout or standing in for
`WebDriverWait`'s own internal sleep; pragma'd, with the reason inline next
to it and a pointer to this note. `_start_browser()` itself is tested by
replacing `webdriver.Chrome` with a fake that records the `Options` it was
given (Selenium's `Options.arguments` is a public list), proving the
persistent-profile and headless configuration without launching Chrome.

### load_data.py, models.py, orm_queries.py: error paths and unreached CLIs

Most of each module ran already, indirectly, through `insert_records()` and
ORM calls elsewhere in the suite. What was missing were specific branches
nothing else reaches: the `PG*` fallback when `DATABASE_URL` is unset, a
connection refused (port `1`, instant and reliable), a failed statement
(`SELECT` against a table that does not exist), blank-to-`None` conversion
for every field type, `_resume()`'s zero-rows and prior-run-found cases, and
each module's own `main()`. `models.py`'s `_verify_mapping()` mismatch branch
is tested by faking the SQLAlchemy inspector's `get_columns()` result rather
than corrupting the real test schema to force a mismatch; the match branch
runs for real, against the schema `load_data.create_table()` actually
builds, so it is a genuine proof the ORM model is still in sync, not a
coverage formality.

### app.py: two branches, two helper functions

`run_in_background()` (the real, non-testing runner) and the lambda
`make_scraper()` returns are never reached, because every test app passes
`testing=True` and an explicit `scraper`. Tested directly: `run_in_background`
with a `threading.Event` the job sets (a synchronization primitive, not a
fixed-duration `sleep()`, with a generous timeout only as a hang safety net);
`make_scraper` with `app.scrape_new_records` monkeypatched to a recorder,
proving the returned closure is bound to the right `session_factory` without
attempting a real scrape. The two `SQLAlchemyError` branches
(`/update-analysis` and `/analysis`, both 503) needed a `query` fake that
raises, which nothing had exercised.

### Pragma count: 9, all named, both sanctioned categories

Eight `__main__` blocks, one per `src/` module that has one. One real-Selenium-
timeout branch in `scrape._fetch_html()`. Under the limit of ten; none widen
an existing pragma to cover more than its one line or block.

### Closed: the scraper orchestration had zero coverage

Caught during Phase 1 review, not planned up front: `test_buttons.py` fakes
the whole `scraper` callable at the `create_app()` boundary, exactly as the
assignment asks ("should be faked / mocked"). That is correct for testing the
route's contract, but it meant `pull_data.scrape_new_records()`,
`_scrape_new_pages()`, `_standardize()`, and every function in `clean.py` ran
under zero tests: not a style gap, a behavioral one. Nothing proved the real
stop-at-the-database's-newest-id logic, the record filtering, or the LLM
subprocess output handling actually worked.

Closed with a new file, `tests/test_pull_pipeline.py`, marked `buttons`
(the marker's canonical text, from the assignment's own required
`pytest.ini` block, is `"Pull Data" and "Update Analysis" behavior`, not
"button endpoints" - testing what Pull Data's pipeline actually does fits
that text, even invoked one level below the Flask route). It calls
`scrape_new_records()` for real, with a fake browser and a fake LLM process,
proving the real orchestration logic. Required two more injection seams,
added following the exact pattern already in place:

- `_scrape_new_pages()` / `scrape_new_records()` gained `fetch_html`.
  `scrape._fetch_html()` drives a real Selenium `WebDriverWait`; a test
  exercising the "page never arrived" branch through it would block for the
  real 30-second timeout. `fetch_html` is injected separately from
  `browser_factory` so a fake can answer instantly while the driver
  argument's contract stays untouched.
- `scrape_new_records()` now threads its `sleep` argument through to
  `_scrape_new_pages()`, which it previously dropped silently. A genuine
  two-page pagination test (following a "Next" link) would otherwise hit a
  real `PAGE_DELAY` (2 seconds) between pages - caught only because the test
  that needed two pages ran slow until this was fixed.

Measured result: `pull_data.py` 37% -> 87%, `scrape.py` 27% -> 39%,
`clean.py` 23% -> 83%. All 11 new tests run in 0.02s with no database.
`scrape.py`'s remaining gap is almost entirely `scrape_data()`, `_resume()`,
and `save_data()`: the Module 2 one-time historical-pull functions, which the
Module 3/4 Pull Data button never calls (it uses `_start_browser`,
`_build_url`, `_next_cursor`, and `_page_path` directly). These still count
toward `--cov=src`'s 100% and are not yet covered or pragma'd; next to
address.

## Phase 3: CI

`.github/workflows/tests.yml` is scaffolded with a Postgres 16 service and
`working-directory: module_4`. Push, confirm a green run, screenshot it to
`module_4/actions_success.png`.

## Phase 4: docs (COMPLETE)

Content done: `orm_queries.py`'s twelve runner functions (`q1` through
`uq2`, `dataset_summary`, `all_results`) all have docstrings now, mirroring
`query_data.py`'s wording exactly for the ten that answer the same
questions, since the two are meant to be read as parallel answers to the
same analysis. `overview.rst`, `architecture.rst`, `testing.rst`, and
`operations.rst` are filled in; `index.rst` and `api.rst` needed no changes.

`architecture.rst` carries the JSON-versus-redirect decision and the
injection-seam table; `operations.rst` carries the busy-state and
uniqueness policy, including why Update Analysis is gated now when Module 3
deliberately allowed it, matching the README's carried-over-changes section.
`testing.rst` carries the marker table (rewritten as a `list-table`: the
scaffolded simple table was malformed RST, with cell text such as
`` ``integration`` `` wider than the column the `====` header declared),
the fixture/test-double reference, and the same "why the suite grew past
five files" story as the README.

**Build verified clean**, exactly as documented (`sphinx-build -b html docs
docs/_build/html`, no `-n`, no `-W` needed): zero warnings, zero errors.
Checked separately with `-n -W` (nitpicky): found 6 broken `:func:`/`:class:`
cross-references, all in the new content, all because `conf.py` does not
set `private-members` so autodoc never generates pages for underscore-
prefixed functions; fixed by switching those six to plain code literals,
since they are implementation details explained in prose, not part of the
linkable public API. 8 nitpick-only warnings remain, all pre-existing
(`api.rst`'s `automodule` directives surfacing SQLAlchemy's own type hints
and `DeclarativeBase`-inherited docstrings, e.g. `MetaData`, `_RegistryType`),
not introduced by anything in this phase, and harmless either way:
`.readthedocs.yaml` already sets `fail_on_warning: false`, and they do not
appear under the actual build command at all, only under `-n`.

Published. The repo went public (checked first: `.env` has never been
committed in this repo's history, and no password/secret-shaped string is
committed anywhere, so going public exposed ordinary coursework, not
credentials), Read the Docs connected via its GitHub App after the repo's
OAuth App connection needed a resync to see it, and the first build went
green on the first try at
<https://jhu-software-concepts-5thlegionnaire.readthedocs.io/en/latest/>
(verified live, not just assumed from the build log). Linked from both
places in `module_4/README.md`: the header line and the `## Documentation`
section.

Section titles the source references by name, confirmed present in the
README: **Additional columns** (`models.py`), **LLM standardizer setup**
(`pull_data.py`), **Validity ranges** (`query_data.py`).

## Rubric traceability

| Pts | Category | Where it is earned |
|----|----|----|
| 5  | Repo setup and submission | layout + public repo + Canvas match |
| 8  | Structure and testability | phase 0: `create_app` seam, `PullState`, `data-testid`, `DATABASE_URL` |
| 13 | Flask page and button behavior | `test_flask_page.py`, `test_buttons.py` |
| 8  | Busy state, error path, determinism | `test_buttons.py` gating and failure tests |
| 14 | Analysis formatting and database | `test_analysis_format.py`, `test_db_insert.py` |
| 8  | Integration | `test_integration_end_to_end.py` |
| 14 | Organization, markers, coverage | `pytest.ini`, `coverage_summary.txt` |
| 8  | GitHub Actions CI | `tests.yml` + `actions_success.png` |
| 17 | Sphinx documentation | `docs/` + published RTD link in README |
| 5  | README, requirements, deliverables | final pass |

## Known ambiguities, resolved

- The prose says 100% coverage "across all modules" but the supplied
  `pytest.ini` scopes `--cov=module_4/src`. Following the `pytest.ini`.
- The supplied `pytest.ini` uses `--cov=module_4/src`, which only resolves
  from the repo root, while `pytest.ini` itself sits in `module_4`. Using
  `--cov=src` and running from `module_4`. Same scope, actually runnable.
