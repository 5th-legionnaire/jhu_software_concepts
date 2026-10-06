# jhu_software_concepts

JHU EN 605.256, Modern Software Concepts in Python. Joshua Latz (jlatz1).
One folder per module. **Active work: `module_5`.** Do not modify `module1`,
`module_2`, `module_3`, or `module_4`; they are graded and committed.
`module_4` is frozen as the Module 5 baseline (commit `1ecf2c9`).

## Module 5 scope

Software assurance and secure SQL on the Grad Cafe service carried over from
Module 4: Pylint 10.00, psycopg SQL composition, LIMIT enforcement, a
least-privilege database role, packaging, pydeps, Snyk, and a GitHub Actions
pipeline. The plan, requirement matrix, and rubric breakdown are in
`module_5/PLAN.md`. Read it before changing code.

## How work proceeds

- Phases in `module_5/PLAN.md` run in order. Before a phase:
  `scripts/gate.sh entry <N>`. At its exit: `scripts/gate.sh <N>`, commit as
  `M5 phase N: <title>`, then `scripts/gate.sh log <N> "<notes>"` and commit
  that as `M5 phase N: gate log`. Stop for Josh's review after each phase.
- Every design change from Module 4 needs a row in `module_5/CHANGES.md` and a
  README subsection anchored `chg-XX`, giving the problem, the decision, the
  trade-off, and the tests. No code change lands without its row; the gate
  (G7) enforces it.
- If the plan is wrong, record a numbered amendment under the phase in
  `PLAN.md` and mirror it in the README's "Changes to the plan" section.

## Layout

```
module_5/
  src/        application code, flat modules (app, scrape, clean, load_data,
              models, orm_queries, pull_data, query_data, templates/, static/)
  tests/      all test code; conftest.py holds the fixtures, doubles, and
              the hook that rejects unmarked tests; snapshots/ holds the
              Module 4 parity snapshots
  scripts/    gate.sh, check_change_register.py, check_secrets.py,
              capture_m4_snapshots.py
  docs/       Sphinx project (conf.py + rst)
  data/       bulk JSON, never imported, never covered
  .gate/      gitignored per-phase logs and Pylint scores
  pytest.ini  markers, --strict-markers, --cov-fail-under=100 against src/
  CHANGES.md  Change Register
.github/workflows/tests.yml   Module 4 CI; leave untouched
.readthedocs.yaml             RTD build config; repointed only in Phase 11
```

## Commands

Run from `module_5/` with `module_5/.venv` (Python 3.14.6), because
`pytest.ini` scopes coverage to `src/` relative to itself.

```bash
cd module_5
pytest                                   # the full suite; no marker selection
pylint --rcfile=.pylintrc src
scripts/gate.sh <N>
sphinx-build -b html docs docs/_build/html
```

## Hard constraints

- `src/` modules import each other flatly (`from models import ...`). Do not
  convert `src/` into a package or rewrite those imports.
- No test may touch the live internet, launch a real browser, run a real
  scrape, or call `sleep()`. Busy state must be observable and injectable.
- No hardcoded secrets, credentials, or absolute paths in code or tests.
- Every test carries at least one marker registered in `pytest.ini`: `web`,
  `buttons`, `analysis`, `db`, `integration`, `security`. Collection fails
  otherwise.
- Never satisfy the 100% coverage gate by executing a line without asserting
  on its result, and never widen `# pragma: no cover`. Zero inline
  `# pylint: disable` in `src/`; fix the code (decision D6).
- New `src/` files must lint 10.00/10 the moment they are created.

## Style

Match the existing Module 3 and 4 code: module docstring with a "Contains:"
block, Google-style docstrings on public functions, comments that explain why
rather than what. No em dashes or double hyphens in prose or docstrings. When
renumbering carried-over code, change attribution bylines only; provenance
references to earlier modules stay.
