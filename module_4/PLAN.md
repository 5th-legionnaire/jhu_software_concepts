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

## Phase 1: tests

`tests/` already holds the five required files with every rubric line stubbed
as a skipped test. Work the skips off one at a time, running the suite after
each. Fill `conftest.py` fixtures first; three of them currently raise
`NotImplementedError` by design (`fake_rows`, `clean_db`, `app`).

Two fixtures need rewriting against the phase 0 contract rather than filling
in as stubbed:

- `app` must pass `testing=True`, which is what selects `run_inline`. Without
  it the default runner is a background thread and the suite goes
  nondeterministic.
- The `web` and `analysis` tests take a `query` fake and no `clean_db`, so
  they need no database. Only `db` and `integration` tests take `clean_db`.

`clean_db` should build the table with `load_data.create_table` rather than
`Base.metadata.create_all`, so the schema under test is the production one,
column comments and `ON CONFLICT` target included.

## Phase 2: coverage to 100

Run `pytest` and work `term-missing` top down. Expected trouble spots:

- `scrape.py` imports Selenium at module scope and builds a Chrome driver.
  Inject a driver factory; pragma only the driver construction itself.
  `scrape_data()` and `_fetch_html()` are now the only uninjected Selenium
  callers left, since `pull_data` takes a `browser_factory`.
- `__main__` blocks in every module. `# pragma: no cover` with a reason on
  each. Done already in `app.py` and `pull_data.py`.
- `check_llm.py`, `run_llm.sh`, and `llm_hosting/` are deliberately outside
  `src/` so they do not count. Leave them there.
- `orm_queries.py` and `query_data.py` each carry a `main()` and an `_sql()`
  debug helper that only the CLI reaches. Cover them with a session double
  rather than pragma: they are pure result formatting.
- Commit the terminal summary to `module_4/coverage_summary.txt`.

## Phase 3: CI

`.github/workflows/tests.yml` is scaffolded with a Postgres 16 service and
`working-directory: module_4`. Push, confirm a green run, screenshot it to
`module_4/actions_success.png`.

## Phase 4: docs

`docs/` is scaffolded with `conf.py` and six pages, each carrying TODOs.
Fill overview, architecture, testing, and operations. `api.rst` already
autodocs all eight modules. Build locally, then make the repo public and
connect Read the Docs. Link the published URL from `module_4/README.md`.

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
