# Module 4 execution plan

EN 605.256, Module 4: Pytest and Sphinx. 100 points. Source of truth is
`assignment/Module 4 - Testing and Documentation Assignment.pdf`.

## Phase 0: refactor contract (do this first, before writing any test)

The Module 3 app cannot satisfy the rubric as written. Four changes, in order.

1. **`create_app()` becomes injectable.** Signature:
   `create_app(scraper=None, loader=None, query=None, database_url=None, testing=False)`.
   Each defaults to the real implementation, so running `python src/app.py`
   is unchanged. Tests pass fakes. This is the seam the whole suite hangs on.

2. **The button routes return JSON, not redirects.** Today `pull()` and
   `update()` flash and redirect. The rubric requires:
   - `POST /pull-data` -> `200` or `202` with `{"ok": true}` when not busy
   - `POST /update-analysis` -> `200` when not busy
   - either route while busy -> `409` with `{"busy": true}` and no work done
   - scraper or loader failure -> non-200 with no partial write

   Keep the browser experience by having the page call these with fetch, or
   accept both (JSON for `Accept: application/json`, redirect otherwise).
   Decide once and document it in `docs/architecture.rst`.

3. **Pull stops being an opaque subprocess.** `pull()` currently spawns
   `pull_data.py` via `subprocess.Popen`, which coverage cannot see into and
   tests cannot drive. Extract the pull into an in-process callable
   (`pull_data.run_pull(scraper, loader)`) and keep the subprocess launch as
   the *default injected* behavior for the real app only. Tests call the
   in-process path.

4. **Busy state becomes observable.** Replace `process.poll()` with an
   explicit flag or small state object on the app that tests can set and read
   directly. No `sleep()` anywhere in the suite.

Also in phase 0:
- Add `DATABASE_URL` support in `load_data.get_db_config()`, preferring it and
  falling back to the existing `PG*` variables.
- Add `data-testid="pull-data-btn"` and `data-testid="update-analysis-btn"` to
  `src/templates/index.html`.
- Confirm the analysis route path. The rubric says `GET /analysis`; Module 3
  serves the page at `/`. Register `/analysis` (keep `/` as an alias) rather
  than hoping the grader tries the root.

## Phase 1: tests

`tests/` already holds the five required files with every rubric line stubbed
as a skipped test. Work the skips off one at a time, running the suite after
each. Fill `conftest.py` fixtures first; four of them currently raise
`NotImplementedError` by design.

## Phase 2: coverage to 100

Run `pytest` and work `term-missing` top down. Expected trouble spots:

- `scrape.py` imports Selenium at module scope and builds a Chrome driver.
  Inject a driver factory; pragma only the driver construction itself.
- `__main__` blocks in every module. `# pragma: no cover` on each.
- `check_llm.py`, `run_llm.sh`, and `llm_hosting/` are deliberately outside
  `src/` so they do not count. Leave them there.
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
| 8  | Structure and testability | phase 0 items 1 and 4, `data-testid`, `DATABASE_URL` |
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
