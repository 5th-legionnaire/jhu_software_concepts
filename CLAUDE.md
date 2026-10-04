# jhu_software_concepts

JHU EN 605.256, Modern Software Concepts in Python. Joshua Latz (jlatz1).
One folder per module. **Active work: `module_4`.** Do not modify `module1`,
`module_2`, or `module_3`; they are graded and committed.

## Module 4 scope

Add a Pytest suite, 100% coverage, GitHub Actions CI, and Sphinx docs to the
Grad Cafe analytics service carried over from Module 3. The full requirement
and rubric breakdown is in `module_4/PLAN.md`. Read it before changing code.

## Layout

```
module_4/
  src/        application code (app, scrape, clean, load_data, models,
              orm_queries, pull_data, query_data, templates/, static/)
  tests/      all test code; conftest.py holds the fixtures and doubles
  docs/       Sphinx project (conf.py + rst)
  data/       bulk JSON, never imported, never covered
  pytest.ini  markers and --cov-fail-under=100 against src/
.github/workflows/tests.yml   CI: Postgres service + full marked suite
.readthedocs.yaml             RTD build config
```

## Commands

Always run pytest from `module_4/`, because `pytest.ini` scopes coverage to
`src/` relative to itself.

```bash
cd module_4
pytest -m "web or buttons or analysis or db or integration"
pytest -m "web or buttons or analysis or db or integration" > coverage_summary.txt
sphinx-build -b html docs docs/_build/html
```

## Hard constraints

- `src/` modules import each other flatly (`from models import ...`).
  `tests/conftest.py` puts `src/` on `sys.path`. Do not convert `src/` into a
  package or rewrite those imports; it breaks parity with Module 3.
- No test may touch the live internet, launch a real browser, run a real
  scrape, or call `sleep()`. Busy state must be observable and injectable.
- No hardcoded secrets, credentials, or absolute paths in code or tests.
- Every test carries at least one marker: `web`, `buttons`, `analysis`, `db`,
  `integration`. An unmarked test is a rubric deduction.
- `DATABASE_URL` is the primary connection setting. The existing `PG*`
  variables stay as a fallback so Module 3 behavior is unchanged.
- Coverage is `--cov-fail-under=100`. Prefer dependency injection over
  `# pragma: no cover`. Where a pragma is unavoidable (driver bootstrap,
  `if __name__ == "__main__"` blocks), add a one-line reason beside it.

## Style

Match the existing Module 3 code: module docstring with a "Contains:" block,
Google-style docstrings on public functions, comments that explain why rather
than what. No em dashes or double hyphens in prose or docstrings.
