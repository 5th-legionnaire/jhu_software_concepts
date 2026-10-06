# Module 5 execution plan

EN 605.256, Module 5: Software Assurance and Secure SQL (SQLi Defense).
100 points plus 5 extra credit. Joshua Latz (jlatz1).

Source of truth: `assignment/Module 5 - Software Assurance + Secure SQL (SQLi Defense) Assignment.pdf`.
When this plan and the PDF disagree, the PDF wins and this plan gets an amendment.

**Status:** v2, approved for implementation. Baseline is `module_4` at commit `1ecf2c9`.
**Hard deadline:** Mon 2026-10-05, 23:59 ET (extension). Canvas zip and GitHub push are both due by then.

## How to use this plan (for Claude Code)

1. **Phases run in order, and every phase is gated.** Before starting a phase, confirm its **Entry**
   checks. A phase is done only when `scripts/gate.sh <N>` passes (section 3) and the phase's **Exit**
   checks hold. Then commit as `M5 phase N: <title>`, append a row to the Gate Log (section 11), and
   mark the heading `(COMPLETE)`.
2. **Every design change from Module 4 gets a Change Register entry** (section 4) with a crisp
   rationale and the test IDs that verify it. The gate script refuses to pass if a change listed for
   the current phase has no rationale, no README section, or a test ID that pytest cannot collect.
   No code change lands without its register row.
3. If the plan turns out to be wrong, stop, record a numbered **Amendment** under the phase (as
   `module_4/PLAN.md` did), then continue.
4. Never modify `module1`, `module_2`, `module_3`, or `module_4`. `.github/workflows/tests.yml` stays
   untouched. `.readthedocs.yaml` is repointed only in Phase 11.
5. Style: match the Module 3 and 4 code. Each module gets a docstring with a "Contains:" block, public
   functions get Google-style docstrings, and comments explain why rather than what. Do not use em
   dashes or double hyphens in prose, docstrings, or comments. **New files must lint clean
   (10.00/10) the moment they are created.** Carried-over files are fixed by Phase 6.

---

## 0. Decisions locked

| # | Decision | Choice | Why |
|---|---|---|---|
| D1 | DB role model | **Two roles:** `gradcafe_owner` (DDL, bulk load) and `gradcafe_app` (runtime) | Pull Data writes, so runtime cannot be read-only. A third role adds a second connection config for little marginal assurance. |
| D2 | User-input surface | **JSON API only:** `GET /api/applicants` | The current app accepts no user input that reaches SQL. This adds the smallest surface that can demonstrate Identifier, Placeholder, LIMIT clamping, and malicious-input handling. |
| D3 | Snyk CI gate | `snyk test --severity-threshold=high` **fails** the job. Snyk Code runs **report-only**. | A real shift-left gate, without a low-severity transitive finding blocking the build. |
| D4 | Snyk account | **None yet.** Signup happens on a parallel track (section 2). | |
| D5 | Env var contract | `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` are primary. `DATABASE_URL` is an optional override. `PG*` is removed. | These are the assignment's literal names. CI and tests need the single-URL override. |
| D6 | Pylint policy | Fix the code. **Zero** inline `# pylint: disable`. `.pylintrc` carries only `source-roots` and `exclude-too-few-public-methods` for SQLAlchemy declarative bases. | A pylintrc that raises thresholds reads as gaming the score. Every baseline message is fixable in code (the largest class was verified). |
| D7 | Dependency source of truth | `setup.py` (`install_requires` plus a `dev` extra). `requirements.txt` is a fully pinned lock from `uv pip compile`. | `uv pip sync` does **not** resolve transitive dependencies. Module 4's top-level-only file would produce an environment without Werkzeug or Jinja2. |
| D8 | Packaging shape | Flat modules: `package_dir={"": "src"}`, `py_modules=[...]`. The **supported install is `pip install -e .`**. | Preserves the Module 4 import contract. Known limitation: a non-editable `pip install .` would not carry `templates/` and `static/`. The README states this. |
| D9 | Entry module name | Keep `src/app.py`. | The expected tree is "should resemble", and the PDF's pydeps example uses `app.py`. |
| D10 | Report | Built collaboratively in Phase 10, format and toolchain decided then. | |
| D11 | Read the Docs | Repoint `.readthedocs.yaml` to `module_5` as the **last** step (Phase 11), after tagging the Module 4 commit so its docs stay reachable as an RTD version. | Repointing replaces what `latest` serves. The tag keeps the Module 4 docs live while that grade is pending. |

---

## 1. Baseline findings (measured, not assumed)

Measured on Python 3.14.6, pylint 4.1.2 / astroid 4.3.3, pydeps 3.0.9, Graphviz `dot`, psycopg 3.3.6.

**Pylint on `module_4/src`: 8.36/10, 51 messages.**

| Count | Message | Location | Fix (change ID) |
|---|---|---|---|
| 19 | E1102 `not-callable` | `func.count()` in `orm_queries.py`, `models.py` | Known astroid false positive on `sqlalchemy.func`. Import from `sqlalchemy.sql.functions`. **Verified to clear.** (CHG-16) |
| 9 | C0301 `line-too-long` | `query_data.py` SQL, `app.py` | Removed by the Phase 3 rewrite. Wrap the rest. (CHG-05, CHG-17) |
| 6 | C0304 `missing-final-newline` | 6 files | `.editorconfig` plus fixes (CHG-17) |
| 5 | W0212 `protected-access` | `pull_data.py` → `scrape._start_browser`, `_fetch_html`, `_build_url`, `_page_path`, `_next_cursor` | Promote to public API (CHG-14) |
| 2 | E1136 `unsubscriptable-object` | `sessionmaker[Session]` annotations | Quoted annotation. **Verified to clear.** (CHG-16) |
| 2 | W0718 `broad-exception-caught` | `app.py:337`, `pull_data.py:317` | Named exceptions plus a `finally` (CHG-10) |
| 2+2 | R0913/R0917 too many (positional) args | `create_app` (6), `scrape_data` (9) | Parameter objects (CHG-09, CHG-15) |
| 1 | R0914 `too-many-locals` | `scrape_data` | Extract the page loop (CHG-15) |
| 2 | R0903 `too-few-public-methods` | `Base`, `Applicant` | `.pylintrc` exclusion (CHG-17) |
| 1 | R1711 `useless-return` | `app.py:110` | Remove (CHG-17) |

**SQL inventory.**

| File | Statement | Problem |
|---|---|---|
| `query_data.py` | `Q3`, `Q4`, `Q6`, `Q7`, `Q8`, `Q9`, `UQ1` | Built with **f-strings** (constants, but the rubric line is absolute) |
| `query_data.py` | All 11 | No LIMIT. Plain strings. `_one()` and `_rows()` take a raw string. |
| `load_data.py` | `_count_rows` | No LIMIT, plain string |
| `load_data.py` | `INSERT_APPLICANT`, `CREATE_APPLICANTS_TABLE` | Parameterized but not composed |
| `orm_queries.py` | 12 builders, `dataset_summary` | No `.limit()` (only `fetch_one` has one) |
| `pull_data.py` | newest-entry select | No `.limit()` |
| `models.py` | `_verify_mapping` count | No `.limit()` |

**User input reaching SQL today: none.** D2 fixes this.

**Least-privilege blocker:** `pull_data.load_records()` calls `create_table()` on every pull.
`CREATE TABLE IF NOT EXISTS` checks schema CREATE privilege before it checks whether the table exists,
and `COMMENT ON` requires ownership. Under `gradcafe_app`, **Pull Data would fail** (CHG-11).

**Verified in a spike:**
- pydeps plus Graphviz build `dependency.svg` from `src/app.py` on 3.14.
- `uv pip compile setup.py --extra dev` yields a full 59-package lock including Werkzeug, Jinja2, pylint and pydeps.
- psycopg `Composed.as_string(None)` renders without a connection, so builders are unit-testable offline.
- A hostile identifier renders safely quoted: `"gpa""; DROP TABLE x; --"`.

---

## 2. Deadline execution (tonight)

The full plan is roughly 5 to 6 hours of work. Two things are wall-clock bound rather than effort
bound, so they start **now, in parallel**, while Claude Code works Phases 0 to 3:

**Parallel track A, Josh (about 20 minutes):**
1. Sign up at snyk.io with GitHub SSO (free plan).
2. `brew tap snyk/tap && brew install snyk-cli && snyk auth`.
3. In the Snyk org settings, **enable Snyk Code**. It is off by default, and `snyk code test` fails until it is on.
4. Copy the API token, then `gh secret set SNYK_TOKEN -R 5th-legionnaire/jhu_software_concepts`.
5. `brew install graphviz` if `dot -V` fails.

**Parallel track B, Josh (about 10 minutes):** confirm local PostgreSQL superuser access
(`psql -c "select current_user, rolsuper from pg_roles where rolname = current_user limit 1"`), since
Phase 5 bootstraps the roles with it.

**Cut line.** If Phase 6 has not passed its gate by **22:30**, defer these to a post-submission
commit. None of them carries rubric points on its own.
- The CI `uv` matrix leg. The local `fresh_install_check.sh` still proves uv.
- Sphinx `security.rst`.
- The informational Snyk scan of `llm_hosting/`.
- The full independent review in Phase 11. A checklist pass replaces it.

**Never cut:** any requirement row R1 to R38, any gate, any Change Register entry, XC1 to XC3.

**Submit by 23:30**, leaving a buffer for the Canvas upload and a CI rerun.

---

## 3. Phase gates

### 3.1 Standard gate: `scripts/gate.sh <N>` (created in Phase 0)

Runs at the **exit** of every phase. Fails fast and prints which check failed.

| # | Check | Command / rule |
|---|---|---|
| G1 | Full suite green, 100% coverage, strict markers | `pytest` (`pytest.ini`: `--cov-fail-under=100 --strict-markers`) |
| G2 | Every test carries a marker | conftest collection hook fails any unmarked test (CHG-18) |
| G3 | Pylint non-regressing | Score ≥ the previous gate's score, recorded in `.gate/scores`. From Phase 6 on: exactly 10.00 with zero messages. |
| G4 | New files lint clean | Every `src/` file added since `1ecf2c9` scores 10.00 on its own |
| G5 | No inline disables | `! grep -rn "pylint: disable" src` |
| G6 | No secrets | `.env` not tracked (`! git ls-files --error-unmatch .env`), and no credential-shaped literal in `src/` or `tests/` (`scripts/check_secrets.py`) |
| G7 | Change Register integrity | `scripts/check_change_register.py <N>`: every CHG row with phase ≤ N is marked `done`, has a rationale, has a README anchor (`#chg-XX`), and lists test node IDs that `pytest --collect-only -q` resolves |
| G8 | Plan hygiene | Gate Log row appended. Phase heading marked `(COMPLETE)`. Amendments recorded if any. |
| G9 | Phase-specific | `case $N` block in `gate.sh` with the phase's own exit checks below |

### 3.2 Standard entry checks (every phase)

- E1: Previous phase has a Gate Log row and its commit is `HEAD` (`git log -1 --format=%s` starts `M5 phase N-1`).
- E2: Working tree clean (`git status --porcelain` empty).
- E3: Active venv is `module_5/.venv` on Python 3.14.6 (`python -c "import sys; print(sys.prefix, sys.version)"`).
- E4: The phase's own entry checks, listed under each phase.

---

## 4. Change Register (Module 4 → Module 5)

Single source: `module_5/CHANGES.md`, in this format. The README's "Changes from Module 4" section has
one subsection per row, anchored `#chg-XX`, carrying the rationale in two to four sentences:
**problem → decision → trade-off accepted**. The report summarizes the table.

| ID | Phase | Change | Rationale (crisp) | Verified by |
|---|---|---|---|---|
| CHG-01 | 1 | `setup.py` with flat `py_modules`. Editable install replaces conftest's `sys.path` hack. | Imports must resolve the same in local runs, tests, and CI. Path hacks hide packaging defects until a grader's machine. Flat modules keep Module 4's import contract. The cost is that non-editable installs lack templates, which is documented. | `test_packaging.py::test_modules_import_from_installed_location`, `::test_no_sys_path_mutation_in_conftest`; `fresh_install_check.sh` |
| CHG-02 | 1 | `requirements.txt` becomes a full lock compiled from `setup.py`. Module 4's annotations move into `setup.py`. | `uv pip sync` installs exactly the file and resolves nothing, so a top-level-only file builds a broken environment. One source (setup.py) and one generated artifact cannot drift. Snyk sees the full tree. | `test_packaging.py::test_lock_pins_every_line`, `::test_lock_includes_tooling`, `::test_lock_includes_transitive_runtime`; CI uv leg |
| CHG-03 | 2 | `DB_*` env contract, `DATABASE_URL` override, `PG*` removed, role-aware `get_db_config(role=)` | The assignment names `DB_*`. Two parallel contracts invite a misconfigured run that silently uses the wrong account. Role selection makes the owner/app split explicit at every call site. | `test_config.py::test_precedence_*`, `::test_owner_role_reads_owner_vars`, `::test_missing_var_names_variable_not_value` |
| CHG-04 | 2 | Connection errors logged sanitized instead of printing the raw exception | libpq errors can echo host and user. Printing them to stdout puts connection details in logs and CI output. | `test_config.py::test_connection_error_message_is_sanitized` |
| CHG-05 | 3 | `query_data.py`: f-string SQL replaced by builders returning `(sql.Composed, params)` and a single executor. Constants become bound params. | The rubric bans f-string SQL outright, and "constants only" is a policy reviewers cannot verify at a glance. Separating build from execute makes every statement inspectable offline and every execution path one function. | `test_sql_guard.py::test_no_sql_string_building`, `::test_every_execute_receives_composable`; `test_query_data.py::test_builder_snapshots`, `::test_parity_with_module_4` |
| CHG-06 | 3 | INSERT and DDL composed from one `COLUMNS` tuple via `Identifier` and `Placeholder` | Two hand-maintained column lists (INSERT text and record mapping) can drift silently. Generating both from one tuple removes the class of bug. | `test_load_data.py::test_insert_builder_columns_match_placeholders`, `::test_insert_round_trip` |
| CHG-07 | 3 | `db_safety.py`: `clamp_limit`, `parse_limit`, `validate_text`. LIMIT on every SELECT (SQL and ORM). | Unbounded reads are a resource-exhaustion vector, and the rubric requires a ceiling. Centralizing the clamp gives one tested definition of "max". Aggregates get an output LIMIT, not an evaluation LIMIT, so analysis answers are unchanged. | `test_db_safety.py::test_clamp_boundaries`, `::test_parse_limit_rejects`, `::test_validate_text_rejects_nul`; `test_sql_guard.py::test_every_select_has_limit` |
| CHG-08 | 4 | New `GET /api/applicants`: whitelisted sort, enum order, parameterized filters, clamped limit, strict param set | No user input reached SQL, so the defenses had nothing to defend. A read-only JSON endpoint is the smallest surface that exercises every rubric control and is fully testable. | `test_applicant_search.py::*`, `test_sqli_malicious.py::*` |
| CHG-09 | 4 | `create_app(services: Services, *, database_url, testing)`. The `Services` dataclass replaces five keyword arguments and adds `search`. | Adding a sixth injected dependency would make `create_app` an unbounded argument list (R0913). One typed seam keeps the Module 4 injection pattern and gives the defaults one home. | `test_flask_page.py::test_services_default_to_real_implementations`, `::test_services_override_is_used` |
| CHG-10 | 6 | Pull route: named exception tuple, busy flag cleared in `finally`, JSON 500 handler | Narrowing the broad `except` alone would let an unlisted error leave `busy=True` forever, turning one failure into a permanent 409. `finally` makes the state correct regardless. | `test_buttons.py::test_unlisted_exception_clears_busy`, `::test_unhandled_error_returns_json_500` |
| CHG-11 | 5 | DDL removed from the runtime pull path. Schema setup is owner-only via `load_data.py`. | The least-privilege app role cannot CREATE or COMMENT, so runtime DDL would break Pull Data. Schema changes are a deployment act, not a request-time act. | `test_pull_pipeline.py::test_load_records_issues_no_ddl`; `test_least_privilege.py::test_pull_succeeds_as_app_role` |
| CHG-12 | 5 | Two roles, `roles.sql`, `grants.sql`, `migrate_ownership.sql` | Module 4 ran as a superuser, so any injection would have had full control. The app role gets SELECT and INSERT on one table, which caps blast radius to reading and adding public applicant rows. | `test_least_privilege.py::test_role_attributes`, `::test_table_privileges`, `::test_ddl_denied[*]` |
| CHG-13 | 5 | Test harness split: `TEST_DATABASE_URL` (app) and `TEST_ADMIN_DATABASE_URL` (owner) | Tests that run as a superuser prove nothing about least privilege. Fixtures need TRUNCATE, which the app must not have. | `test_least_privilege.py::test_app_fixture_connects_as_app_role` |
| CHG-14 | 6 | scrape helpers used by `pull_data` promoted to public names | They were already a cross-module API. The underscore was a false signal and the cause of W0212. | Existing `test_scrape.py` and `test_pull_pipeline.py` tests (renamed), `test_scrape.py::test_public_api_surface` |
| CHG-15 | 6 | `scrape_data(window: ScrapeWindow, options: ScrapeOptions)`; page loop extracted | Nine positional arguments are an error-prone call surface (R0913/R0914). Dataclasses name every knob and keep defaults in one place. | `test_scrape.py::test_options_defaults`, existing scrape tests updated |
| CHG-16 | 6 | SQLAlchemy functions imported from `sqlalchemy.sql.functions`. Quoted `sessionmaker[Session]` annotations. | Clears 21 astroid false positives without disables. There is no behavior change, and compiled SQL is identical. | `test_orm_queries.py::test_compiled_sql_unchanged` (snapshot from Phase 0) |
| CHG-17 | 6 | `.pylintrc` (minimal), `.editorconfig`, line-length and newline fixes | Configuration states where the code lives, not what rules to relax. Formatting is enforced by the editor rather than remembered. | `test_lint_policy.py::test_pylintrc_relaxes_nothing`, `::test_no_inline_disables` |
| CHG-18 | 0 | `pytest.ini`: `security` marker, `--strict-markers`, collection hook rejecting unmarked tests. CI runs the full suite. | Module 4 selected tests by marker expression, so a test carrying only a new marker would silently never run. Running everything and rejecting unmarked tests closes that gap. | `test_lint_policy.py::test_every_collected_test_is_marked` |
| CHG-19 | 9 | `.github/workflows/ci.yml`, four jobs; `tests.yml` untouched | Shift-left: lint, dependency graph, supply chain, and tests each fail independently and visibly. Module 4's workflow keeps that module's grade evidence intact. | Green CI run (`actions_success.png`); `test_ci_config.py::test_four_jobs`, `::test_pylint_fail_under_10`, `::test_svg_validation_step` |
| CHG-20 | 11 | RTD repointed to `module_5`; Module 4 preserved via tag `module-4-final` | Docs should describe current code. The tag keeps the Module 4 docs reachable while that grade is pending. | RTD build log, both versions load |

`test_ci_config.py` parses `ci.yml` with PyYAML, which becomes a dev extra. It is not a substitute for
the green run, but it catches a deleted gate before CI ever runs.

---

## 5. Requirements matrix

| ID | Requirement (PDF wording, condensed) | Pts | Phase | Verification |
|---|---|---|---|---|
| R1 | `module_4/` copied to `module_5/` | | P0 | Tree check |
| R2 | venv in `module_5/`; deps install; app, analysis page, tests run | 3 | P0, P1 | `fresh_install_check.sh`, CI |
| R3 | Pylint 10.00/10 on **only** `module_5/src` | 7 | P6 | `pylint_report.txt`, CI lint |
| R4 | No Pylint errors or warnings | 2 | P6 | Zero message lines |
| R5 | README documents the Pylint command | 1 | P10 | README |
| R6 | No SQL via f-strings, `+`, `.format()`, `%` | 5 | P3 | `test_no_sql_string_building` |
| R7 | psycopg composition (`SQL`, `Identifier`, `Placeholder`/`%s`) | 5 | P3, P4 | Builder tests |
| R8 | User values always parameterized | 4 | P3, P4 | Spy cursor, malicious matrix |
| R9 | Construction separated from execution | 3 | P3 | Builders return `(stmt, params)`, one executor |
| R10 | Malicious input: no crash, no leak, no "everything returned" | 3 | P4 | Section 7.4 matrix |
| R11 | Every query has LIMIT | 2 | P3 | `test_every_select_has_limit` |
| R12 | Max limit enforced (1 to 100) | 2 | P3, P4 | Clamp tests, API tests |
| R13 | Oversized-request abuse prevented | 1 | P4 | 400 or clamp, never 500 |
| R14 | Creds from env, none hard-coded | 3 | P2 | `test_config.py`, G6 |
| R15 | `.env.example`; `.env` gitignored | 2 | P2 | G6, file check |
| R16 | Least-privilege, non-superuser | 3 | P5 | `test_least_privilege.py` in CI |
| R17 | PDF: permissions, why, SQL or screenshot | 2 | P10 | Report |
| R18 | `dependency.svg` via pydeps plus Graphviz | 4 | P7 | File, CI |
| R19 | Graph reflects project structure | 2 | P7 | Review |
| R20 | PDF: 5 to 7 sentence explanation | 2 | P10 | Report |
| R21 | Functional `setup.py`; installable | 3 | P1 | Fresh install, both paths |
| R22 | PDF: why packaging matters | 2 | P10 | Report |
| R23 | `requirements.txt` has runtime and tooling (pylint, pydeps) | 2 | P1 | `test_lock_includes_tooling` |
| R24 | README "Fresh Install", pip **and** uv | 3 | P10 | README, CI |
| R25 | `snyk test` executed | 2 | P8 | Output |
| R26 | `snyk-analysis.png` | 2 | P8 | File |
| R27 | Vulns documented and addressed | 2 | P8, P10 | Report table |
| R28 | `ci.yml` present and functional | 2 | P9 | Green run |
| R29 | CI Pylint `--fail-under=10` | 3 | P9 | Workflow |
| R30 | CI generates and validates `dependency.svg` | 3 | P9 | Workflow |
| R31 | CI runs Snyk | 2 | P9 | Workflow |
| R32 | CI runs pytest, fails on failures | 3 | P9 | Workflow |
| R33 | README: setup, env vars, running, security tooling | 3 | P10 | README |
| R34 | PDF: pip/uv, graph, SQLi, least privilege, LIMIT, CI | 5 | P10 | Report checklist |
| R35 | Deliverables complete and organized | 2 | P11 | Checklist |
| R36 | Correct repo via SSH; `module_5/` organized; Canvas matches GitHub | 5 | P11 | Checklist |
| R37 | Actions success screenshot | | P9 | `actions_success.png` |
| R38 | `coverage_summary.txt` | | P10 | File |
| R39 | Every M4→M5 design change documented, rationalized, tested (Josh's requirement) | | all | G7 |
| XC1 | `snyk code test` executed | +2 | P8 | Output |
| XC2 | Screenshot or output | +2 | P8 | `snyk-code-analysis.png` |
| XC3 | Findings summary and remediation | +1 | P10 | Report |

---

## 6. Target layout

```
.github/workflows/
    tests.yml                 # module_4, untouched
    ci.yml                    # NEW: module_5, four jobs
module_5/
    src/
        app.py                # + GET /api/applicants, Services dataclass
        db_safety.py          # NEW
        applicant_search.py   # NEW
        query_data.py, load_data.py, orm_queries.py, models.py, pull_data.py, scrape.py, clean.py
        templates/, static/
    tests/
        conftest.py           # app vs admin connections; marker hook; no sys.path hack
        test_db_safety.py, test_applicant_search.py, test_sqli_malicious.py,
        test_sql_guard.py, test_least_privilege.py, test_config.py,
        test_packaging.py, test_lint_policy.py, test_ci_config.py      # NEW
        ...module_4 tests, updated
    sql/roles.sql, grants.sql, migrate_ownership.sql                    # NEW
    scripts/gate.sh, check_change_register.py, check_secrets.py,
            fresh_install_check.sh, regen_lock.sh                       # NEW
    .gate/                    # gitignored: per-phase pylint scores and logs
    report/                   # NEW: report source (Phase 10)
    docs/                     # Sphinx, carried over
    data/
    setup.py, requirements.txt, .pylintrc, .editorconfig, .env.example, .gitignore, pytest.ini
    CHANGES.md                # NEW: Change Register
    dependency.svg, snyk-analysis.png, snyk-code-analysis.png, privileges.png, actions_success.png
    pylint_report.txt, coverage_summary.txt, module_5_report.pdf
    README.md, PLAN.md
```

---

## 7. Phases

### Phase 0: Scaffold, baseline, and gate tooling (COMPLETE)

**Entry:** E2 on the repo root. `module_4` suite green with Module 4's own instructions. Python 3.14.6 available.

**Tasks**
1. `cp -R module_4 module_5`, excluding `.venv`, `pull_work/`, `__pycache__`, `.coverage`. Replace
   `assignment/` contents with the M5 PDF.
2. Repo-root `CLAUDE.md`: active module is `module_5`, `module_4` is frozen, and point to this plan,
   the gate script, and the Change Register rule.
3. Create the venv on 3.14.6 and install from Module 4's `requirements.txt`.
4. Capture snapshots for the parity tests **before any change**:
   - `query_data.run_all()` output on the seeded fixture DB → `tests/snapshots/m4_run_all.txt`
   - Compiled SQL of every ORM statement → `tests/snapshots/m4_orm_sql.txt`
5. Create `scripts/gate.sh`, `check_change_register.py`, `check_secrets.py`, `CHANGES.md` (all rows
   `planned`), `.gate/` (gitignored), `.editorconfig`, and a minimal `.pylintrc` (`source-roots=src` only for now).
6. CHG-18: `pytest.ini` gains `security` and `--strict-markers`, plus the conftest collection hook
   that fails unmarked tests.
7. Replace "Module 4" with "Module 5" in each `src/` header docstring.
8. Record the baseline Pylint score (8.36 expected) in `.gate/scores`.

**Exit:** standard gate (G3 baseline is the recorded score) plus:
- 102 Module 4 tests pass, plus the new policy tests. Coverage 100%.
- Snapshots committed. `/analysis` renders against the local DB.
- Running `gate.sh 0` with a deliberately unmarked dummy test fails (then delete the dummy). This proves G2 bites.

**Amendments** (mirrored in README "Changes to the plan")
- **A0.1** E2 did not hold at entry: task 1 was already done in `19a3d0f`, and this v2 plan was an
  uncommitted edit at entry. Josh committed it as `5b2b2b0` during Phase 0. The copied `.venv`, `pull_work/`, `__pycache__/`,
  and `.coverage` were deleted, and the venv was rebuilt, since its scripts pointed at `module_4/.venv`.
  `PLAN.md` was already in `module_5/`.
- **A0.2** The measured baseline is **8.30/10 with 52 messages** (20 E1102, not 19), on the same
  toolchain. G3's baseline is 8.30. CHG-16 clears 22 false positives, not 21.
- **A0.3** Module 4's lock has no Pylint, so `pylint==4.1.2` was installed separately for the
  baseline. Phase 1 adds it to `setup.py`.
- **A0.4** The parity snapshot is seeded with the full committed `data/llm_extend_applicant_data.json`
  (30,000 rows), not the two conftest rows, which leave Q5, Q8, and Q9 at zero. Both snapshots were
  captured from the frozen `module_4/src` by `scripts/capture_m4_snapshots.py`. The Phase 3 parity
  test must seed the same file (about 2 s).
- **A0.5** G8 checks the *previous* phase's row and heading. `gate.sh log N` writes this phase's row
  after the commit, and only if `HEAD^{tree}` equals the tree that passed the gate. The row is
  committed as `M5 phase N: gate log`, so E1 still holds.
- **A0.6** G4 treats a `src/` file as new when `module_4/src` has no file of that name, since all of
  `module_5/` postdates `1ecf2c9`.
- **A0.7** G6 honors one time-boxed exception, the conftest literal
  `postgres:postgres@localhost/gradcafe_test`, until Phase 2.
- **A0.8** `CHANGES.md` adds a Status column. A row with no test reference must say `Evidence:`.
- **A0.9** The `tests/conftest.py` byline was also updated to Module 5, because the file is edited here.

### Phase 1: Packaging and reproducible environment (CHG-01, CHG-02) (COMPLETE)

**Entry:** standard. `uv --version` works.

**Tasks**
1. `setup.py`:
   ```python
   setup(
       name="gradcafe-analytics",
       version="5.0.0",
       description="Grad Cafe admissions analytics: scraper, PostgreSQL loader, Flask analysis page.",
       author="Joshua Latz",
       python_requires=">=3.14",
       package_dir={"": "src"},
       py_modules=["app", "applicant_search", "clean", "db_safety", "load_data",
                   "models", "orm_queries", "pull_data", "query_data", "scrape"],
       install_requires=[  # runtime only, compatible-release ranges, commented per package
           "Flask~=3.1", "psycopg[binary]~=3.3", "SQLAlchemy~=2.0", "python-dotenv~=1.0",
           "beautifulsoup4~=4.15", "selenium~=4.49", "urllib3~=2.7",
       ],
       extras_require={"dev": [
           "pylint~=4.1", "pydeps~=3.0", "pytest~=8.4", "pytest-cov~=7.0", "pytest-mock~=3.15",
           "PyYAML~=6.0", "sphinx~=8.2", "sphinx-rtd-theme~=3.0",
       ]},
   )
   ```
   `db_safety` and `applicant_search` are listed now. Phase 1 creates them as docstring-only stubs so
   the editable install resolves, and Phases 3 and 4 fill them in.
2. `scripts/regen_lock.sh`: `uv pip compile setup.py --extra dev -p 3.14 -o requirements.txt`.
   No hashes, because `pip install -r` with hashes rejects the editable line a grader will run next.
3. Delete the `sys.path` insertion in `tests/conftest.py`.
4. `scripts/fresh_install_check.sh` clones `HEAD` into a temp dir and, for each installer:
   - pip: `python3.14 -m venv .venv && pip install -r requirements.txt && pip install -e . --no-deps`
   - uv: `uv venv -p 3.14 && uv pip sync requirements.txt && uv pip install -e . --no-deps`

   Then it runs the import smoke test, `pylint --version`, `pydeps --version`, and
   `pytest -m "not db and not integration"`.
5. Write `test_packaging.py`.

**Exit:** standard gate plus: `fresh_install_check.sh` passes both legs. `grep -c "==" requirements.txt`
equals the non-comment line count. CHG-01 and CHG-02 are `done` with README subsections.

**Amendments** (mirrored in README "Changes to the plan")
- **A1.1** The lock is compiled with `--universal --python-version 3.14`, giving 70 entries (Windows-only
  packages behind markers, plus `packaging`), so it is valid on any grader's OS and the Linux runner.
- **A1.2** `packaging~=26.0` is in the `dev` extra because `test_packaging.py` imports it. Two extra tests:
  `test_setup_py_declares_every_src_module`, `test_lock_satisfies_setup_py_ranges`.
- **A1.3** `fresh_install_check.sh --worktree` tests the tree about to be committed (gate G9); no argument
  tests `HEAD` (Phase 11). It copies with `git archive`, not `git clone`.
- **A1.4** The fresh-install pytest run uses `--no-cov`, since deselecting `db` and `integration` would
  fail the 100% gate. The full gate still enforces 100%.
- **A1.5** `*.egg-info/` and `build/` are gitignored (the editable install writes `src/*.egg-info`).
- **A1.6** Two `gate.sh` bugs fixed: the Gate Log row check now searches only from the `## 11. Gate Log`
  heading (earlier tables have rows beginning `| 1 |`), and `log` marks the heading `(COMPLETE)` before
  appending the row, including headings that end in `)`.
- **A1.7** `tests/test_gate_checkers.py` tests `check_secrets.py`, `check_change_register.py`, and
  `gate.sh log` against inputs they must reject, so the gate's own checks cannot loosen unnoticed.

### Phase 2: Configuration and secrets (CHG-03, CHG-04) (COMPLETE)

**Entry:** standard. A local `.env` exists, built from `.env.example`. Josh's real values never get committed.

**Tasks**
1. `get_db_config(database_url=None, role="app")`. Precedence:
   1. The explicit `database_url` argument.
   2. The `DATABASE_URL` env var.
   3. `DB_HOST`, `DB_PORT`, `DB_NAME`, plus `DB_USER`/`DB_PASSWORD` for role `app` or
      `DB_OWNER_USER`/`DB_OWNER_PASSWORD` for role `owner`.

   A missing variable raises `KeyError` naming the variable, never its value.
2. `models.build_url()` follows the same contract.
3. `.env.example`:
   ```
   # Runtime (least-privilege) account the web app and Pull Data use.
   DB_HOST=localhost
   DB_PORT=5432
   DB_NAME=gradcafe
   DB_USER=gradcafe_app
   DB_PASSWORD=change-me
   # Owner account: schema setup and bulk load only. Keep it out of the running app's environment.
   # DB_OWNER_USER=gradcafe_owner
   # DB_OWNER_PASSWORD=change-me
   # Optional single-URL override, used by CI and tests. Takes precedence over DB_*.
   # DATABASE_URL=postgresql+psycopg://gradcafe_app:change-me@localhost:5432/gradcafe
   ```
4. Remove every `PG*` reference from code, docs, and CI env.
5. Sanitize connection error output (CHG-04).
6. Write `test_config.py`.

**Exit:** standard gate plus: `grep -rn "PG\(HOST\|USER\|PASSWORD\|DATABASE\|PORT\)" src tests`
is empty. App starts from `.env`. `git check-ignore -q .env` succeeds.

**Amendments** (mirrored in README "Changes to the plan")
- **A2.1** `.env.example` is a task of this phase, so the entry check's "built from `.env.example`" is
  circular. The local `.env` was migrated by hand (`PG*` keys renamed to `DB_*`, values unchanged).
- **A2.2** `.env.example` uses `DB_NAME=gradcafedb`, Josh's existing database, not `gradcafe`.
- **A2.3** `TEST_DATABASE_URL` is deliberately pulled forward from Phase 5 (CHG-13), because this phase's
  secrets check retires the conftest fallback literal. No default. Offline tests get an unreachable,
  credential-free URL; `clean_db` fails with a message naming the variable. Phase 5 adds
  `TEST_ADMIN_DATABASE_URL` and the app/owner split.
- **A2.4** `tests.yml` keeps its `PG*` variables: it runs Module 4 and must stay untouched. Only
  Module 5's `ci.yml` (Phase 9) is `PG*`-free.
- **A2.5** Tests that prove the `PG*` names are gone build them from parts, so the literal exit grep stays
  empty and meaningful.
- **A2.6** Five stale `Usage (from module_4/)` docstring paths in `src/` now say `module_5/`.
- **A2.7** `docs/*.rst` and the README "Connection settings" section describe `DB_*`. README Module 4
  history sections stay until Phase 10.
- **A2.8** First-pass README update, requested at the Phase 2 review: Module 5 header, status, deliverables
  checklist, overview, structure, Fresh Install (pip and uv), environment-variable table, security-tooling
  commands, with pending items marked. Architecture onward is still the Module 4 baseline until Phase 10.

### Phase 3: SQL composition and LIMIT everywhere (CHG-05, CHG-06, CHG-07) (COMPLETE)

**Entry:** standard. Parity snapshots from Phase 0 are present.

**Rules (enforced by tests)**
1. Every statement given to psycopg `execute`/`executemany` is a `sql.Composable`. A bare `str` fails.
2. Builders return `(stmt, params)` and touch no DB. One executor per module calls `cursor.execute(stmt, params)`.
3. Identifiers go through `sql.Identifier`. Values go through placeholders in `params`, **including
   constants** (GPA/GRE ranges, regex patterns).
4. Every SELECT ends in `LIMIT %(limit)s`, with `limit` from `clamp_limit()`. INSERT and DDL take none.
5. No concatenation, f-string, `.format()`, or `%` formatting near SQL text.

**`db_safety.py`**
```python
MIN_LIMIT, MAX_LIMIT, DEFAULT_LIMIT = 1, 100, 20

def clamp_limit(value: int | None, default: int = DEFAULT_LIMIT) -> int: ...
    # None -> default; below MIN -> MIN; above MAX -> MAX. Pure.

def parse_limit(raw: str | None) -> tuple[int, bool]: ...
    # Strict: optional sign plus at most 6 digits, else LimitError (-> 400).
    # Returns (effective_limit, was_clamped). Rejects "1e3", "10 OR 1=1", " 5", 5000-digit strings.

def validate_text(raw: str | None, field: str, max_len: int) -> str | None: ...
    # Rejects over-length values and control characters including NUL. psycopg raises DataError on
    # NUL in text, which would otherwise surface as a 500.
```

**LIMIT on aggregates (README and PDF).** On `SELECT COUNT(*) ...`, `LIMIT 1` caps rows *returned*,
not rows *evaluated*. The slide's subquery-LIMIT pattern caps evaluation and would silently change
every analysis answer once the table exceeds the limit. So aggregates get an output LIMIT, and the
row-returning API gets the enforced 1 to 100 clamp.

**`query_data.py`:**
- `QUESTIONS` maps names to builders `build_q1` to `build_uq2`. `_execute()` is the module's only
  `execute` call site.
- Single-row aggregates use `clamp_limit(1)`. UQ1 and UQ2 use `clamp_limit(MAX_LIMIT)`.
- The SQL quoted in the README and PDF is rendered from the builders with `as_string(None)`, so the
  docs cannot drift from what runs.

**`load_data.py`:** `INSERT` built as
`sql.SQL("INSERT INTO {t} ({cols}) VALUES ({vals}) ON CONFLICT ({pk}) DO NOTHING")`, with both column
lists generated from one `COLUMNS` tuple. `CREATE TABLE` composed. `_count_rows` gets `LIMIT 1`.

**ORM:** `.limit(clamp_limit(1))` on single-row statements, `.limit(clamp_limit(MAX_LIMIT))` on
grouped ones, including `pull_data` and `models._verify_mapping`.

**Tests**
- `test_sql_guard.py::test_no_sql_string_building` (static): AST walk of `src/*.py`. Fails on any
  f-string, string `+` or `%`, or `.format()` whose literal text matches
  `\b(SELECT|INSERT|UPDATE|DELETE|CREATE|ALTER|DROP|FROM|WHERE|LIMIT)\b`, and reports file:line.
- `::test_every_execute_receives_composable` (runtime): a spy cursor records the argument types for
  `run_all`, `insert_records`, and `search_applicants` (the last one added in Phase 4).
- `::test_every_select_has_limit`: every `QUESTIONS` builder, every ORM `*_stmt()`, and the search builder.
- `test_db_safety.py`: boundary tables for 0, 1, 100, 101, -1, `None`, `"abc"`, `"1e3"`, `"9"*5000`, and NUL.
- `test_query_data.py::test_parity_with_module_4`: `run_all` output equals the Phase 0 snapshot.
  **This is the proof the refactor changed no answers.**

**Exit:** standard gate plus: the AST guard reports zero findings, and the parity test passes. To
prove the guard bites, temporarily reintroduce one f-string SQL statement, confirm the gate fails,
then revert.

**Amendments** (mirrored in README "Changes to the plan")
- **A3.1** The plan contradicts itself on `parse_limit`: section 7 says "at most 6 digits", but the Phase 4
  matrix requires `limit=1000000` (seven digits) to return 200 and clamp to 100. The matrix is the
  observable behavior, so the cap is **9 digits**. `1000000` clamps, ten digits and longer are rejected,
  and `int()` never sees a long string.
- **A3.2** The AST guard exempts `.format()` called on a `sql.SQL(...)` literal. That is psycopg's own
  composition API, which quotes what it inserts, and the plan requires `sql.SQL` composition. The guard
  still flags `.format()` on a plain string, and it checks only literal operands of `+` and `%`, so
  `sql.SQL(...) + sql.SQL(...)` is allowed.
- **A3.3** `execute_query` refuses a bare string with `TypeError`, enforcing rule 1 at the one executor.
  Two test helpers that passed strings (`TRUNCATE`, a failing `SELECT`) now pass `sql.SQL`.
- **A3.4** Constants become bound parameters, including the CASE labels (cast with `CAST(... AS TEXT)`,
  so PostgreSQL need not infer a bare parameter's type). The formula's own numbers stay literal: `100.0`
  in a percentage and `0` in `NULLIF`. They are arithmetic, not data, and binding `100.0` would change a
  NUMERIC result to a float. The parity snapshot confirms every answer is unchanged.
- **A3.5** The parity test seeds the full 30,000-row dataset (A0.4). Builder snapshots live in
  `tests/snapshots/m5_query_sql.txt`, rendered by `scripts/render_query_sql.py`.

### Phase 4: `GET /api/applicants` (CHG-08, CHG-09) (COMPLETE)

**Entry:** standard. `db_safety` complete.

**7.4.1 Contract**

| Param | Type | Rule | Bad input |
|---|---|---|---|
| `limit` | int | `parse_limit`. Default 20, clamp 1 to 100. Response reports the effective value. | Non-integer or over 6 chars → 400 |
| `sort` | enum | Whitelist `{"p_id","date_added","gpa","gre","gre_v","gre_aw","term","status","degree"}` → `sql.Identifier` | → 400 |
| `order` | enum | `{"asc": sql.SQL("ASC"), "desc": sql.SQL("DESC")}`. Default `desc`. | → 400 |
| `term`, `status`, `degree`, `nationality` | text | `validate_text(max_len=64)`. `LOWER(col) = LOWER(%(x)s)`. | → 400 |
| `q` | text | `validate_text(max_len=100)`. `program ILIKE %(q)s ESCAPE '\'` with `\ % _` escaped in the value. | → 400 |
| other | | Rejected so the surface stays enumerable | 400 listing allowed params |

The first value wins for repeated params. The projection is fixed and composed from `Identifier`s.
ORDER BY uses `{sort} {order} NULLS LAST, p_id {order}`.

```
200 {"ok": true, "limit": 20, "requested_limit": "500", "clamped": true,
     "sort": "date_added", "order": "desc", "count": 20, "rows": [...]}
400 {"ok": false, "error": "<param and problem; never echoes the raw value>"}
503 {"ok": false, "error": DB_UNREACHABLE}
```

**7.4.2 Implementation:** `parse_search_args(args) -> SearchFilters` (a frozen dataclass; validation),
`build_search(filters) -> (Composed, params)` (pure composition), and
`search_applicants(cursor, filters)` (the executor). The search is injected through `Services.search`
(CHG-09).

**7.4.3 Offline tests (`test_applicant_search.py`, markers `web`, `security`):**
- Builder snapshot for a representative filter set.
- A hostile identifier forced past the whitelist renders quoted.
- Every 400 path, using a fake `search` that fails the test if it is called. This proves validation
  rejects input before any query exists.

**7.4.4 Malicious matrix (`test_sqli_malicious.py`, markers `db`, `security`):** seeded with N known
rows and connected as the app role from Phase 5 on (as the Phase 4 test URL until then). Every case
also asserts: status is not 500, `applicants` still has N rows, and the response holds only
projection columns.

| Input | Expect |
|---|---|
| `term=' OR '1'='1` | 200, 0 rows (not N) |
| `term=Fall 2026'; DROP TABLE applicants; --` | 200, 0 rows, table intact |
| `status=accepted' UNION SELECT usename, passwd FROM pg_shadow --` | 200, 0 rows, no `passwd` key |
| `q=%`, `q=_` | Only rows literally containing `%` or `_` (seed one of each) |
| `q=\` | 200, no SQL error |
| `sort=gpa; DROP TABLE applicants`, `sort=p_id"` | 400 |
| `order=desc; SELECT pg_sleep(5)` | 400, fast |
| `limit=1000000` | 200, `limit == 100`, `count <= 100`, `clamped` true |
| `limit=0`, `limit=-5` | 200, `limit == 1` |
| `limit=abc`, `1e3`, `10 OR 1=1`, `"9"*5000` | 400 |
| `term=%00` | 400, not a `DataError` 500 |
| `term="A"*10000` | 400 |
| Unicode, RTL text, emoji | 200, literal |
| `nationality=american&nationality=' OR 1=1 --` | First value wins, 200 |
| `debug=1` | 400 |

**Exit:** standard gate plus: every row of the matrix is a parametrized test case (count them).
Two cases are spot-checked with `curl` against the running app.

**Amendments** (mirrored in README "Changes to the plan")
- **A4.1** Every plan matrix row is a parametrized case in `test_sqli_malicious.py` (51 tests in all), plus
  extra cases for each sort column, combined filters, ordering, ISO dates, and right-to-left text.
- **A4.2** `SearchFilters` keeps the text filters in one read-only `text` mapping: seven fields exceeded
  Pylint's attribute limit, and D6 forbids a disable.
- **A4.3** The LIKE `ESCAPE` character is a bound parameter, so the SQL text holds no quote character.
- **A4.4** The projection excludes `comments` (free text a client could bulk-read); the plan left it open.
- **A4.5** `requested_limit` is echoed only after the digits-only check.
- **A4.6** The `curl` spot-checks ran read-only against the real local database (30,019 rows, untouched).
- **A4.7** Known gap until CHG-10 (Phase 6): only an unreachable database maps to 503; another database
  error is a bare 500.
- **A4.8** The Phase 3 spy and LIMIT guard tests now cover `search_applicants` and the search statement.

### Phase 5: Least-privilege database (CHG-11, CHG-12, CHG-13) (COMPLETE)

**Entry:** standard. Local superuser access confirmed (track B). `psql --version` works.

**`sql/roles.sql`** (run as superuser: `psql -v owner_pw=... -v app_pw=... -v db=gradcafe -f sql/roles.sql`)
```sql
CREATE ROLE gradcafe_owner LOGIN PASSWORD :'owner_pw'
    NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
CREATE ROLE gradcafe_app LOGIN PASSWORD :'app_pw'
    NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS CONNECTION LIMIT 20;
REVOKE ALL ON DATABASE :"db" FROM PUBLIC;
GRANT CONNECT ON DATABASE :"db" TO gradcafe_owner, gradcafe_app;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;     -- default since PG15, explicit for older servers
GRANT USAGE, CREATE ON SCHEMA public TO gradcafe_owner;
GRANT USAGE ON SCHEMA public TO gradcafe_app;
```
**`sql/grants.sql`** (after the owner creates the table)
```sql
REVOKE ALL ON applicants FROM PUBLIC;
GRANT SELECT, INSERT ON applicants TO gradcafe_app;
-- SELECT: page, API, and the pull's newest-entry read.
-- INSERT: Pull Data. ON CONFLICT DO NOTHING requires no UPDATE.
```
No UPDATE, DELETE, TRUNCATE, REFERENCES, or TRIGGER. No sequence grants (`p_id` is not serial).
No `ALTER DEFAULT PRIVILEGES`.

**`sql/migrate_ownership.sql`:** `ALTER TABLE applicants OWNER TO gradcafe_owner;` then `grants.sql`,
for Josh's existing local DB.

**Code:** remove `create_table()` from `pull_data.load_records()`. `load_data.main()` uses
`get_db_config(role="owner")`. Pull Data maps `InsufficientPrivilege` to a clear message.

**Tests (`test_least_privilege.py`, markers `db`, `security`), as `gradcafe_app`:**
- `test_role_attributes`: `rolsuper`, `rolcreaterole`, `rolcreatedb`, `rolbypassrls` all false.
- `test_table_privileges`: SELECT and INSERT true. UPDATE, DELETE, TRUNCATE false.
- `test_ddl_denied`, parametrized: DROP, ALTER, CREATE TABLE, TRUNCATE, COMMENT ON. Each raises
  `psycopg.errors.InsufficientPrivilege`.
- `test_pull_succeeds_as_app_role`: proves the minimum is also sufficient.
- `test_app_fixture_connects_as_app_role`: guards against the harness quietly running as a superuser.

**Amendments** (mirrored in README "Changes to the plan")
- **A5.1** Josh's database is `gradcafedb`, so the scripts take the name as `-v db`. `migrate_ownership.sql`
  moved the existing table to `gradcafe_owner` and `.env` now connects as `gradcafe_app`. Data untouched,
  reversible with `ALTER TABLE ... OWNER TO`.
- **A5.2** `roles.sql` creates a role only if missing, else updates it (also how a password is rotated);
  `grants.sql` first strips every privilege. Both are safe to rerun.
- **A5.3** No cleartext password is sent, typed, or logged. The plan's `psql -v` would have put it in the process
  list, and `log_min_error_statement=error` would have written a failed `ALTER ROLE ... PASSWORD` to a
  world-readable server log. `roles.sql` instead takes SCRAM-SHA-256 verifiers from the environment
  (`scripts/scram_verifier.py`). Passwords were generated in memory and written only to the gitignored `.env`.
  **Verified:** after provisioning, the real passwords were searched for in the server log, shell and psql
  history, every repository file, the scratch directory, and all setup output: no match. A cleartext login
  works against the stored verifier.
- **A5.4** `PUBLIC` is revoked on the database and the table.
- **A5.5** The Pull Data exit check re-sends a row already in the database: `ON CONFLICT DO NOTHING` still needs
  `INSERT`, and nothing is written to Josh's real data.
- **A5.7** A missing table raises `UndefinedTable`, not a privilege error; `load_records` maps both to one
  clear message (found by the least-privilege tests, with a failing run before the fix).
- **A5.8** `scripts/check_credential_leaks.py` is part of the gate from Phase 5 on: it reads the passwords from
  `.env` and searches the tree, all git history, the server log, and the shell history, printing counts only.
- **A5.9** `REVOKE ALL ON DATABASE FROM PUBLIC` also removes `TEMP` from every account, owner included.
- **A5.10** An unentitled `GRANT` is a warning that does nothing, not an error; the test asserts it changed nothing.
- **A5.6** `privileges.png` (a screenshot of `\dp applicants`) is committed and was compared with the live
  database: owner `arwdDxtm`, `gradcafe_app` `ar`. `privileges.txt` adds `\du` and a per-privilege table.
- **A5.11** Snyk Code was confirmed enabled by running it on one throwaway file outside the repository (it
  authenticated, analyzed, reported 0 issues). Josh asked at the Phase 5 go-ahead for the credential leak
  check, and for it to be tested and documented: it exists because an asserted control is an unverified
  claim, and it is permanent because a one-time search proves only the moment it ran.

**Exit:** standard gate plus:
- No password from `.env` appears in the tree, git history, server log, or shell history
  (`scripts/check_credential_leaks.py`, added by A5.8).
- The app runs locally against `.env` with `DB_USER=gradcafe_app`, and Pull Data works with a faked
  scraper.
- `privileges.png` captured (`\du` and `\dp applicants`).
- `rolsuper` is false for the account in `.env`.

### Phase 6: Pylint 10.00/10 (CHG-10, CHG-14, CHG-15, CHG-16, CHG-17)

**Entry:** standard. Phases 3 to 5 complete, so the SQL rewrite has already removed most line-length hits.

**Tasks:** work the section 1 table.
- **CHG-10 (stuck-busy trap):** `job()` clears busy in `finally`; catch
  `PULL_FAILURES = (PullError, psycopg.Error, SQLAlchemyError, OSError, WebDriverException)`; register
  `@app.errorhandler(500)` returning the JSON error shape.
- **CHG-15:** `scrape_data(window: ScrapeWindow, options: ScrapeOptions | None = None)`. Extract `_scrape_pages()`.
- **CHG-16:** verify the compiled ORM SQL equals the Phase 0 snapshot.
- **Final `.pylintrc`:**
  ```ini
  [MAIN]
  source-roots=src
  [DESIGN]
  exclude-too-few-public-methods=sqlalchemy.orm.*
  ```
- Run `pylint --rcfile=.pylintrc --fail-under=10 src > pylint_report.txt` from `module_5/`.

**Exit:** standard gate (G3 is now exactly 10.00 with zero message lines) plus: `pylint_report.txt`
committed. `test_compiled_sql_unchanged` passes. Behavior parity holds (the run_all snapshot still passes).

**Amendments** (decided 2026-10-05 during the Phase 0 review, mirrored in README "Changes to the plan")
- **A6.1** Phase 3 adds a LIMIT to every ORM statement, so the compiled SQL can no longer equal the
  Phase 0 snapshot. `test_compiled_sql_unchanged` instead asserts, for every `*_stmt()` builder, that the
  compiled text is the Phase 0 snapshot text followed by exactly one trailing `LIMIT` clause, and that
  the bound parameters are the snapshot's parameters plus that one limit value. The Phase 0 snapshot is
  never re-captured, so the test shows the LIMIT is the only change across Phases 3 and 6.

### Phase 7: Dependency graph

**Entry:** standard. `dot -V` works. Pylint at 10, so the module structure is final.

**Tasks**
1. From `module_5/`: `pydeps src/app.py --noshow -T svg -o dependency.svg`. The default
   `--max-bacon=2` shows the first ring of third-party packages. Tune `--cluster` or `--max-bacon`
   only if it is unreadable, and record the final flags.
2. Draft the 5 to 7 sentences, covering:
   - `app` as the hub.
   - The psycopg path (`query_data`, `load_data`, `applicant_search`) and the ORM path (`models`, `orm_queries`).
   - The ETL chain `pull_data → scrape → clean → load_data`.
   - `db_safety` as the shared leaf.
   - What each external package does.

**Exit:** standard gate plus: the SVG shows every `src/` module and both new modules. The explanation
draft is stored in `report/` for Phase 10.

### Phase 8: Snyk (required plus extra credit)

**Entry:** standard, plus track A done: `snyk whoami` succeeds, Snyk Code is enabled, and
`gh secret list` shows `SNYK_TOKEN`.

**Tasks**
1. In the active venv with the lock installed (Snyk inspects the installed environment):
   `snyk test --file=requirements.txt --package-manager=pip --command=python`.
   Screenshot → `snyk-analysis.png`. Save `--json` output to `snyk_report.json`.
2. For each finding: upgrade in `setup.py`, regenerate the lock, and re-run; or remove the package; or
   document why it does not apply. Any upgrade re-runs the full gate, since dependency bumps can change behavior.
3. `snyk code test` → `snyk-code-analysis.png` and `snyk_code_report.txt`. Triage each finding as
   fixed (commit reference), false positive (reasoning), or accepted risk. Any code fix gets a CHG row
   and a test.
4. Informational, and cut-line eligible: scan `llm_hosting/requirements.txt` and document the result.

**Exit:** standard gate plus: zero high or critical findings in `snyk test`, or each one justified in
writing. Both screenshots committed. A triage table is drafted for the report.

### Phase 9: GitHub Actions CI (CHG-19)

**Entry:** standard. `SNYK_TOKEN` secret present. Local gate green at Phase 8.

```yaml
name: module-5-ci
on:
  push:          { paths: ["module_5/**", ".github/workflows/ci.yml"] }
  pull_request:  { paths: ["module_5/**", ".github/workflows/ci.yml"] }
  workflow_dispatch:
defaults: { run: { working-directory: module_5 } }

jobs:
  lint:              # R29
    - setup-python 3.14.6 (cache pip) → pip install -r requirements.txt → pip install -e . --no-deps
    - pylint --rcfile=.pylintrc --fail-under=10 src

  dependency-graph:  # R30
    - apt-get install -y graphviz → install as above
    - pydeps src/app.py --noshow -T svg -o dependency.svg
    - test -s dependency.svg && grep -q "<svg" dependency.svg
    - upload-artifact dependency.svg

  snyk:              # R31, D3
    - install as above
    - uses: snyk/actions/setup@master
    - snyk test --file=requirements.txt --package-manager=pip --severity-threshold=high
    - snyk test --json > snyk_report.json || true → upload-artifact
    - snyk code test || true → upload-artifact
    - skip with a notice when SNYK_TOKEN is unavailable (fork PRs)

  test:              # R32, R2
    strategy.matrix.installer: [pip, uv]      # uv leg is cut-line eligible
    services.postgres: postgres:16 (superuser used ONLY to bootstrap roles)
    - create db; psql -f sql/roles.sql with -v passwords from workflow env
    - owner creates table; psql -f sql/grants.sql
    - env TEST_DATABASE_URL (gradcafe_app), TEST_ADMIN_DATABASE_URL (gradcafe_owner)
    - pytest
```

Interpretations: "4 separate actions" means four jobs in one `ci.yml`. The PDF's "pytest fail if
score is below 10" means fail on any test failure, with the 100% coverage gate on top.

**Exit:** standard gate plus: `test_ci_config.py` passes. One push yields **all four jobs green**,
captured in `actions_success.png`. To prove the lint job bites, push a throwaway branch with one lint
violation and confirm it fails red, then delete the branch.

### Phase 10: Documentation and report

**Entry:** standard. All evidence files exist.

**README.md (module_5).** Module 4's structure and depth, plus:
1. Deliverables checklist at the top.
2. **Changes from Module 4**: one subsection per CHG row, anchored `#chg-XX`, giving problem →
   decision → trade-off, and linking to its tests.
3. **Fresh Install**: pip and uv side by side, the editable install and why (D8), and lock regeneration.
4. **Environment variables**: table of every `DB_*` variable, which role uses it, and where it is read.
5. **Database setup**: superuser bootstrap → `roles.sql` → owner load → `grants.sql` → app. Plus `migrate_ownership.sql`.
6. **Security tooling**: exact Pylint, pydeps, `snyk test` and `snyk code test` commands, and how to read each.
7. **SQL safety model**: the five rules, LIMIT semantics, and the `/api/applicants` contract.
8. **Testing**: the security tests, the malicious matrix, the gate script.
9. **CI**: four jobs and what each enforces.
10. **Known issues and limitations**: non-editable install, `llm_hosting` findings, Snyk free-tier caps.

**Report (`module_5_report.pdf`):** built together in this phase. Required content, in rubric order:
- pip/uv install
- packaging rationale
- dependency graph with 5 to 7 sentences
- SQLi defenses, with before/after from `Q7` and the matrix results
- LIMIT enforcement
- least privilege (SQL, rationale, `privileges.png`)
- Snyk findings and remediation
- Snyk Code findings and triage (extra credit)
- CI workflow (`actions_success.png`)
- Change Register summary

`coverage_summary.txt`: `pytest > coverage_summary.txt`.

**Exit:** standard gate (G7 now also checks that every README anchor exists) plus: a report checklist
covering every R17, R20, R22, R27, R34 and XC3 topic. Every README command was copy-pasted into a
fresh shell and worked.

### Phase 11: Verification, submission, RTD (CHG-20)

**Entry:** standard. CI green on `HEAD`.

**Tasks**
1. **Independent review** (cut line: checklist only). A fresh Claude Code session that has not seen
   the implementation gets only the PDF and the repo, and walks section 5 row by row.
2. Run `fresh_install_check.sh` against the pushed commit.
3. Zip `module_5/`, excluding `.venv`, `__pycache__`, `.coverage`, `pull_work/`, `.gate/` and `.env`.
   Diff the zip listing against `git ls-files module_5`.
4. Submit the Canvas zip and the SSH URL `git@github.com:5th-legionnaire/jhu_software_concepts.git`
   **by 23:30**.
5. **After submitting:**
   - Tag `module-4-final` at `1ecf2c9` and activate it as an RTD version.
   - Repoint `.readthedocs.yaml` to `module_5/docs/conf.py` and `module_5/requirements.txt`.
   - Confirm both `latest` (M5) and `module-4-final` (M4) build and load.
6. Keep the repo public until grading completes.

**Exit:** the submission checklist is fully ticked, CI is green on the submitted commit, and both RTD
versions load.

---

## 8. Definition of done

- [ ] `pylint --rcfile=.pylintrc --fail-under=10 src` → 10.00/10, zero messages, zero disables
- [ ] `pytest` → green, 100% coverage, every test marked
- [ ] Guard, LIMIT, malicious-matrix, and least-privilege suites pass as `gradcafe_app`
- [ ] Analysis answers identical to Module 4 (parity snapshot)
- [ ] Every CHG row `done`, with a README rationale and passing tests (G7)
- [ ] Both fresh-install paths pass from a clean clone
- [ ] All evidence files committed
- [ ] `ci.yml` green, four jobs
- [ ] Canvas zip matches the GitHub commit
- [ ] RTD serves Module 5 on `latest` and Module 4 on `module-4-final`

---

## 9. Rubric traceability

| Rubric category | Pts | Requirement IDs |
|---|---|---|
| GitHub repository setup and submission | 5 | R36, R35 |
| Virtual environment and reproducible setup | 8 | R2, R23, R24 |
| Pylint compliance | 10 | R3, R4, R5 |
| SQL injection defenses and query refactoring | 20 | R6, R7, R8, R9, R10 |
| LIMIT enforcement and query safety controls | 5 | R11, R12, R13 |
| Database hardening and least privilege | 10 | R14, R15, R16, R17 |
| Dependency analysis and graph | 8 | R18, R19, R20 |
| Packaging and setup.py | 5 | R21, R22 |
| Snyk dependency security analysis | 6 | R25, R26, R27 |
| GitHub Actions CI pipeline | 13 | R28, R29, R30, R31, R32 |
| README, PDF documentation, final deliverables | 10 | R33, R34, R35 |
| **Extra credit:** Snyk Code | +5 | XC1, XC2, XC3 |

---

## 10. Known ambiguities, resolved

| Ambiguity | Resolution |
|---|---|
| "4 separate actions" | Four jobs in one `ci.yml` |
| "Pytest ... fail if score is below 10" | Fail on any test failure; the coverage gate stays |
| "Every query must have an inherent LIMIT" | Every SELECT. Aggregates get an output LIMIT. |
| "Queries that use user input" when none exist | D2 adds the surface. All SQL is converted anyway. |
| "If your app is read-only..." | It isn't. SELECT plus INSERT, and DDL moves to the owner. |
| `DB_*` "for example" vs `DATABASE_URL` | `DB_*` primary, URL override (D5) |
| Expected tree shows `flask_app.py` | Kept `app.py` (D9) |
| "uv can extract requirements from setup.py" | Used literally (D7) |
| psycopg2 in the study guide vs psycopg 3 in code | Same `sql` module API. Noted in the PDF. |

---

## 11. Gate Log

Appended by `gate.sh` at each phase exit.

| Phase | Completed (ET) | Commit | Tests | Coverage | Pylint | Notes |
|---|---|---|---|---|---|---|
| baseline | 2026-10-05 | 1ecf2c9 | 102 | 100% | 8.36 | module_4 HEAD |
| 0 | 2026-10-05 20:06 | 13acd9f | 107 | 100.00% | 8.30 | Scaffold, snapshots, gate tooling, CHG-18. Pylint baseline 8.30 measured (plan said 8.36); amendments A0.1 to A0.9. |
| 1 | 2026-10-05 20:34 | 2bd7d2b | 114 | 100.00% | 8.30 | setup.py, universal 70-pin lock, editable install, fresh install with pip and uv; amendments A1.1 to A1.5. |
| 2 | 2026-10-05 21:53 | a00ebfa | 189 | 100.00% | 8.31 | DB_* config with roles, sanitized connection errors, .env.example, TEST_DATABASE_URL pulled forward, README first pass; amendments A2.1 to A2.8. |
| 3 | 2026-10-05 22:01 | 48b2a49 | 333 | 100.00% | 8.52 | Composed SQL, LIMIT everywhere, db_safety, parity with Module 4 over 30,000 rows; amendments A3.1 to A3.5. |
| 4 | 2026-10-05 22:08 | 439845e | 443 | 100.00% | 8.68 | GET /api/applicants, Services seam, 51-case malicious-input matrix, live curl spot-checks; amendments A4.1 to A4.8. |
| 5 | 2026-10-05 22:28 | c65c87c | 509 | 100.00% | 8.68 | Least-privilege roles, SCRAM verifiers, permanent credential leak check, privileges.txt and privileges.png; real DB migrated; amendments A5.1 to A5.11. |
