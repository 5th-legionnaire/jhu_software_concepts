# EN 605.256 Modern Software Concepts in Python: Module 5

**Name:** Joshua Latz
**JHED ID:** jlatz1
**Module:** Module 5, Assignment: Software Assurance and Secure SQL (SQLi Defense)
**Repository:** `git@github.com:5th-legionnaire/jhu_software_concepts.git`. This assignment lives under `module_5/`.
**Documentation:** <https://jhu-software-concepts-5thlegionnaire.readthedocs.io/en/latest/>
(still serving Module 4 until Read the Docs is repointed at the end of Module 5, with Module 4 kept
reachable at the `module-4-final` tag)
**Python:** 3.14.6 (CPython, macOS)
**PostgreSQL:** 18.6 (Homebrew)

> **Note on section references.** Headings in this README are not numbered. The
> Module 3 README numbered them, and source comments referred to numbers such as
> "section 5.2"; renumbering during this module broke those references silently.
> Source comments now name headings by title instead.

## Status

This README is a **first pass, written while Module 5 is being built.** The
build follows [PLAN.md](PLAN.md) in gated phases. Each phase must pass
`scripts/gate.sh` (tests, 100% coverage, Pylint, secrets scan, Change Register)
before it is committed, and the [Gate Log](PLAN.md) records each result.
**Complete as of this commit: Phases 0 to 4** (scaffold and gate tooling;
packaging and the pinned lock; configuration and secrets; SQL composition and
`LIMIT`; the search endpoint). **Not started:** the least-privilege
database role, Pylint 10.00/10, the dependency graph, Snyk, the CI workflow,
and the PDF report. Sections below that describe those are marked *pending*.
The sections from "Architecture" onward still describe the Module 4 baseline
and are brought up to date in Phase 10.

Two sections are maintained from the first phase on: every design change from
Module 4, and every change to the plan itself.

## Changes from Module 4

One subsection per row of the Change Register, [CHANGES.md](CHANGES.md). Each
gives the problem, the decision, and the trade-off accepted, and names the
tests that verify it. `scripts/gate.sh` refuses to pass a phase whose rows lack
a subsection here.

<a id="chg-01"></a>

### CHG-01: `setup.py` and an editable install replace the `sys.path` edit

**Problem.** Module 4's `tests/conftest.py` put `src/` on `sys.path` so that
the flat modules (`from models import ...`) would import. Imports resolved
one way under pytest and another way everywhere else. A packaging defect,
such as a module that nothing declared, would stay hidden until the code ran
on someone else's machine.

**Decision.** `setup.py` declares the application as flat modules,
`package_dir={"": "src"}` with an explicit `py_modules` list, and the
supported install is editable:

```bash
pip install -r requirements.txt
pip install -e . --no-deps
```

The conftest path edit is gone. Imports now resolve the same way in local
runs, tests, and CI. Two new modules, `db_safety` and `applicant_search`,
are declared and exist as empty stubs until Phases 3 and 4 fill them in.
This keeps Module 4's import contract: no `src/` file changed its imports.

**Trade-off.** A non-editable `pip install .` would not carry `templates/`
and `static/`, because flat modules have no package to hold package data.
Only the editable install is supported.

**Verified by.**
`tests/test_packaging.py::test_modules_import_from_installed_location`. Every
declared module imports, and from `module_5/src`.
`::test_setup_py_declares_every_src_module` keeps `py_modules` in step with
`src/`. `::test_no_sys_path_mutation_in_conftest`.
`scripts/fresh_install_check.sh` installs a clean copy with pip and with uv
and runs the suite in each.

<a id="chg-02"></a>

### CHG-02: `requirements.txt` is a full lock generated from `setup.py`

**Problem.** Module 4's `requirements.txt` listed top-level packages only.
`uv pip sync` installs exactly what the file lists and resolves nothing. From
that file it would build an environment without Werkzeug or Jinja2, in which
Flask cannot start. Snyk would also see only part of the dependency tree.

**Decision.** `setup.py` is now the only place dependencies are edited:
runtime in `install_requires`, tooling in a `dev` extra, each with the reason
for it carried over from Module 4's annotations. `scripts/regen_lock.sh` runs
`uv pip compile setup.py --extra dev --universal` to produce
`requirements.txt`, which pins all 70 packages, transitive ones included,
with platform markers where a package is OS-specific. It has no hashes,
because `pip install -r` with hashes would reject the editable install that
follows. Every runtime pin is the same version Module 4 used.

**Trade-off.** The lock is generated, so a hand edit to it is overwritten.
Changing a dependency means editing `setup.py` and rerunning
`scripts/regen_lock.sh`.

**Verified by.** `tests/test_packaging.py::test_lock_pins_every_line`,
`::test_lock_includes_tooling` (pylint, pydeps),
`::test_lock_includes_transitive_runtime` (Werkzeug, Jinja2),
`::test_lock_satisfies_setup_py_ranges`. That last test fails if `setup.py`
is edited without regenerating the lock. The uv leg of
`scripts/fresh_install_check.sh` runs too.

<a id="chg-03"></a>

### CHG-03: `DB_*` variables, role-aware `get_db_config`, and no `PG*`

**Problem.** The assignment names `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`,
and `DB_PASSWORD`. Module 4 read `DATABASE_URL` first and five `PG*` variables
as a fallback. Keeping both would leave two parallel contracts, so a
misconfigured run could use the wrong account without anyone noticing. Module 5
also needs two accounts, a runtime one and an owner (Phase 5), and nothing in
Module 4 said which a call site meant.

**Decision.** `get_db_config(database_url=None, role="app")` resolves in this
order: the explicit argument, then `DATABASE_URL`, then `DB_HOST`, `DB_PORT`,
and `DB_NAME` with `DB_USER` and `DB_PASSWORD` for `app` or `DB_OWNER_USER` and
`DB_OWNER_PASSWORD` for `owner`. The `PG*` variables are not read at all.
`models.build_url()` follows the same contract. A missing variable raises
`KeyError` naming the variable and never a value, and an unknown role raises
`ValueError`. `.env.example` documents every variable, and the app role never
borrows the owner's credentials, so a missing `DB_USER` fails rather than
falling through.

**Trade-off.** An existing Module 4 `.env` stops working until its keys are
renamed. `DATABASE_URL` is the one override that applies to both roles, as
planned: if it names the app account, a run asking for the owner role gets
the app account, and its DDL then fails loudly with a privilege error rather
than succeeding as the wrong user.

**Verified by.** `tests/test_config.py`: `test_precedence_*` (explicit URL beats
`DATABASE_URL` beats `DB_*`), `test_owner_role_reads_owner_vars`,
`test_missing_var_names_variable_not_value` (parametrized over every variable),
`test_pg_variables_are_no_longer_read`, `test_no_source_file_reads_a_pg_variable`,
and `test_env_example_lists_every_variable_the_code_reads`.

<a id="chg-04"></a>

### CHG-04: connection errors are logged sanitized

**Problem.** `create_connection()` printed the driver's exception text. libpq
writes the host, port, and user name into that text, for example `connection to
server at "db.internal" (10.0.0.9), port 5432 failed: FATAL: password
authentication failed for user "gradcafe_app"`. Printing it puts connection
details into terminals and CI logs.

**Decision.** It now logs at `ERROR` the exception's type and a fixed hint to
check that PostgreSQL is running and the `DB_*` settings are correct. The
driver's text is not logged.

**Trade-off.** A developer no longer sees why the connection failed. A
wrong password and a stopped server read the same, and the way to tell them
apart is `psql` with the same settings. `execute_query()` still prints
statement errors unchanged: they are not connection errors, and Phase 3
revisits them when the SQL is rewritten.

**Verified by.**
`tests/test_config.py::test_connection_error_message_is_sanitized` feeds a
realistic libpq message and asserts that none of its host, address, port, or
user name appears in the log or on stdout or stderr.

<a id="chg-05"></a>

### CHG-05: SQL is built, then executed, and never assembled from strings

**Problem.** `query_data.py` held its eleven analysis queries as text
constants, seven of them built with f-strings. The values spliced in were
constants, so nothing was exploitable, but "constants only" is a policy a
reviewer cannot verify at a glance, and the assignment forbids f-string SQL
outright. Construction and execution were also tangled: `_one()` and `_rows()`
took raw strings.

**Decision.** Each question has a builder, `build_q1()` through `build_uq2()`,
that returns `(statement, params)`. The statement is a psycopg `sql.Composed`:
identifiers go through `sql.Identifier`, values through `sql.Placeholder`, and
static text is a `sql.SQL` literal. A builder touches no database, so the exact
text is inspectable without a connection (`statement.as_string(None)`), and
`QUESTIONS` maps every question to its builder. One function, `_execute()`,
is the only place the module calls `cursor.execute`. Constants became bound
parameters too: the term, status, degree and nationality values, the GPA and
GRE ranges, the regular expressions, and even the labels in the `CASE`
expressions. `load_data.execute_query()` now refuses anything that is not a
`sql.Composable`.

**Trade-off.** The formula's own numbers stay literal: `100.0` in a
percentage and `0` in `NULLIF`. They are arithmetic, not data, and binding
`100.0` would turn a NUMERIC result into a float. The statements are harder to
read as Python than a SQL string was; `tests/snapshots/m5_query_sql.txt` and
`scripts/render_query_sql.py` render them back to plain SQL.

**Verified by.** `tests/test_sql_guard.py`: `test_no_sql_string_building` walks
every `src/*.py` and fails on an f-string, a string `+` or `%`, or `str.format`
holding SQL, and `test_guard_reports_sql_built_from_strings` shows it does so.
`test_every_execute_receives_composable` wraps a real cursor in a spy and
records the type of every statement `run_all` and `insert_records` send.
`tests/test_query_data.py::test_builder_snapshots` pins the rendered SQL, and
`::test_parity_with_module_4` runs `run_all` over all 30,000 rows and compares
it line for line with what Module 4 printed.

<a id="chg-06"></a>

### CHG-06: the INSERT and the DDL are generated from one column tuple

**Problem.** The column list lived twice by hand: in the INSERT text, and in
the record mapping that feeds it. A column added to one and not the other
fails silently, as a missing value or an error at the first insert.

**Decision.** `load_data.COLUMNS` lists every column with its SQL type. The
`CREATE TABLE`, the column names and the placeholders of the `INSERT`, and the
`ON CONFLICT` target are all composed from it with `sql.Identifier` and
`sql.Placeholder`. The row count is composed too, and carries a `LIMIT`.

**Trade-off.** The SQL types stay as `sql.SQL` text inside the tuple, since a
type is syntax and not a value. They are fixed source text, not input.

**Verified by.** `tests/test_load_data.py`:
`test_insert_builder_columns_match_placeholders`,
`test_record_mapping_covers_exactly_the_table_columns` (the other hand-written
list), and `test_insert_round_trip`, which loads rows, reads them back, and
shows a rerun adds none.

<a id="chg-07"></a>

### CHG-07: every SELECT has a LIMIT, from one definition of "maximum"

**Problem.** No query was bounded. An unbounded read is a resource-exhaustion
risk the moment any request can influence it, and the assignment requires a
ceiling.

**Decision.** `src/db_safety.py` defines `MIN_LIMIT`, `MAX_LIMIT` and
`DEFAULT_LIMIT` as 1, 100 and 20, and `clamp_limit()`. Every statement ends in
a limit from it: single-row aggregates use `clamp_limit(1)` and grouped
results `clamp_limit(MAX_LIMIT)`, in the raw SQL, in every ORM statement, and
in the pull's and the model check's reads. `parse_limit()` and
`validate_text()` are the boundary for request text, ready for Phase 4: they
reject what they cannot make safe, and their errors name the field and never
echo the value.

**Trade-off.** On `SELECT COUNT(*)`, `LIMIT 1` caps the rows *returned*, not
the rows *evaluated*. A subquery limit would cap evaluation and silently change
every analysis answer once the table outgrew it, so aggregates get an output
limit, and the row-returning API gets the enforced 1 to 100 clamp. The parity
test is what shows no answer changed. See also amendment A3.1.

**Verified by.** `tests/test_db_safety.py`: `test_clamp_boundaries`,
`test_parse_limit_rejects`, and the text-validation tests.
`tests/test_sql_guard.py`: `test_every_select_has_limit` for each of the eleven
builders, `test_every_orm_statement_builder_is_limited`, and
`test_every_select_the_orm_executes_has_limit`, which captures what SQLAlchemy
actually sends.

<a id="chg-08"></a>

### CHG-08: a search endpoint gives the defenses something to defend

**Problem.** The application accepted no input that reached SQL, so the
assignment's controls (parameters, identifier quoting, a limit ceiling,
malicious-input handling) had nothing to apply to.

**Decision.** `GET /api/applicants` is the smallest surface that exercises all
of them: read-only, a fixed projection, and a strict parameter set.

| Parameter | Rule | Bad input |
| --- | --- | --- |
| `limit` | digits only, at most 9; clamped to 1 to 100; default 20; the response reports the effective value | `400` |
| `sort` | one of `p_id`, `date_added`, `gpa`, `gre`, `gre_v`, `gre_aw`, `term`, `status`, `degree`; reaches SQL through `sql.Identifier`; default `date_added` | `400` |
| `order` | `asc` or `desc`, looked up in a table of two fixed fragments; default `desc` | `400` |
| `term`, `status`, `degree`, `nationality` | at most 64 characters, no control characters; `LOWER(column) = LOWER(%(value)s)` | `400` |
| `q` | at most 100 characters; `program ILIKE %(q)s ESCAPE %(escape)s`, with `\`, `%` and `_` escaped in the value so a client's wildcards match themselves | `400` |
| anything else | rejected, so the surface stays enumerable; the error lists the allowed names and does not echo the unknown one | `400` |

The first value of a repeated parameter wins. Rows come back as `p_id`,
`program`, `date_added`, `url`, `status`, `term`, `us_or_international`, `gpa`,
`gre`, `gre_v`, `gre_aw`, `degree`, `llm_generated_program` and
`llm_generated_university`; free-text `comments` are deliberately left out.
Results are ordered by `{sort} {order} NULLS LAST, p_id {order}`.

```text
200 {"ok": true, "limit": 100, "requested_limit": "1000000", "clamped": true,
     "sort": "p_id", "order": "desc", "count": 100, "rows": [...]}
400 {"ok": false, "error": "sort must be one of: p_id, date_added, ..."}
503 {"ok": false, "error": "The database could not be reached. ..."}
```

The work is in three steps that never mix, in `src/applicant_search.py`:
`parse_search_args()` validates request text into a frozen `SearchFilters`,
`build_search()` composes the statement with no database, and
`search_applicants()` executes it. A rejected request never builds a statement.

**Trade-off.** Every error message names the field and the rule but never the
value, so a developer must read the request to see what was wrong. Nothing
else reaches the client: an unexpected database error is not caught here (see
A4.7).

**Verified by.** `tests/test_applicant_search.py` (offline): every `400` path,
run through the real route with a search that fails the test if it is called;
builder snapshots; a hostile identifier forced past the whitelist renders
quoted. `tests/test_sqli_malicious.py` (database): 51 cases, each also
asserting the status is not `500`, the table still holds every seeded row, and
every returned row has exactly the projection's columns.

<a id="chg-09"></a>

### CHG-09: `create_app` takes one `Services` object

**Problem.** `create_app` had five keyword arguments for its injected
dependencies. The search made a sixth, and an argument list that grows with
every dependency is a function nobody can call from memory. Pylint also
counts it (`too-many-arguments`).

**Decision.** `create_app(services=None, *, database_url=None, testing=False)`.
`Services` is a frozen dataclass of `scraper`, `loader`, `query`, `runner` and
`search`, every one optional. A field left unset becomes the real
implementation, in one place, `with_defaults()`. A test names only what it
fakes: `create_app(Services(search=fake), testing=True)`.

**Trade-off.** Every existing call site had to change from keyword arguments to
a `Services(...)`. `create_app()` with no arguments, which is how
`python3 src/app.py` and Module 3 call it, is unchanged.

**Verified by.** `tests/test_flask_page.py::test_services_default_to_real_implementations`,
`::test_services_override_is_used`, `::test_services_is_frozen_and_every_field_is_optional`.

<a id="chg-18"></a>

### CHG-18: The whole suite runs, and an unmarked test stops it

**Problem.** Module 4 ran its tests by marker expression
(`pytest -m "web or buttons or analysis or db or integration"`). Module 5 adds
a `security` marker. A test carrying only that marker would have been
deselected and never run, and nothing would have reported it.

**Decision.** `pytest.ini` now runs every collected test with no marker
selection. It adds `--strict-markers`, so a misspelled marker is an error, and
registers `security`. A collection hook in `tests/conftest.py` stops the
session before any test runs if a test carries none of the markers that
`pytest.ini` declares, and lists every offender by node ID. The hook reads the
markers from `pytest.ini` itself. pytest's own marker list also contains
built-ins such as `parametrize` and `skipif`, and a test carrying only one of
those would otherwise have passed the check. A test caught this while the hook
was being written.

**Trade-off.** The Module 4 command still works, but it is no longer the
command of record. Plain `pytest` from `module_5/` is.

**Verified by.**
`tests/test_lint_policy.py::test_every_collected_test_is_marked`,
`::test_unmarked_items_reports_only_tests_without_an_allowed_marker`,
`::test_collection_hook_rejects_an_unmarked_test_by_name`. `scripts/gate.sh 0`
also adds an unmarked dummy test, confirms collection fails and names it, then
deletes the dummy.

## Changes to the plan

[PLAN.md](PLAN.md) records each amendment under the phase that raised it.
This list mirrors them.

### Phase 0 amendments

- **A0.1 Entry state.** The copy (task 1) had already been made in commit
  `19a3d0f`, and the v2 plan was an uncommitted edit, so check E2 (clean tree)
  did not hold at entry. Josh committed the plan as `5b2b2b0` during
  Phase 0. The copied
  `.venv`, `pull_work/`, `__pycache__/`, and `.coverage` were untracked
  duplicates of Module 4's. They were deleted, and the venv was rebuilt,
  because its scripts still pointed at `module_4/.venv`.
- **A0.2 Pylint baseline is 8.30, not 8.36.** It was measured on the same
  toolchain (pylint 4.1.2, astroid 4.3.3, Python 3.14.6). There are 52
  messages, not 51: 20 `not-callable` false positives on `func.count()`, not
  19. CHG-16 therefore clears 22 false positives, not 21. G3's baseline is the
  measured 8.30.
- **A0.3 Pylint installed outside the lock.** Module 4's `requirements.txt`
  has no Pylint, so `pylint==4.1.2` was installed into the venv separately to
  take the baseline. Phase 1 adds it to `setup.py` and the lock.
- **A0.4 Parity snapshot uses the full dataset.** The snapshot is seeded with
  all 30,000 rows of the committed `data/llm_extend_applicant_data.json`, not
  the two conftest rows. Two rows leave Q5, Q8, and Q9 at zero, so a broken
  regex or range bind could pass the parity test unnoticed. The snapshots were
  captured from the frozen `module_4/src` by the new
  `scripts/capture_m4_snapshots.py`. The Phase 3 parity test seeds the same
  file, which takes about 2 seconds.
- **A0.5 Gate Log timing.** A Gate Log row records its phase's commit, so it
  cannot exist when the gate runs. The gate (G8) checks the previous phase's
  row and heading instead. After the phase commit, `scripts/gate.sh log N`
  appends the row and marks the heading. It refuses to do so unless the
  commit's tree is the exact tree that passed the gate. The row is committed as
  `M5 phase N: gate log`, which still satisfies E1.
- **A0.6 "New `src/` files" for G4.** All of `module_5/` was added after
  `1ecf2c9`, so G4 treats a file as new when `module_4/src` has no file of
  that name.
- **A0.7 One time-boxed secrets exception.** Module 4's conftest falls back to
  `postgres:postgres@localhost/gradcafe_test` for the local test database.
  `scripts/check_secrets.py` allows that one literal until Phase 2 and fails
  on it from then on, when tests move to environment-only URLs.
- **A0.8 Change Register format.** `CHANGES.md` adds a Status column. A row
  with no test reference must say `Evidence:` (CHG-20, the Read the Docs
  check).
- **A0.9 Test header byline.** Task 7 names `src/` only. `tests/conftest.py`
  is edited in this phase, so its attribution byline was also updated to
  Module 5. Provenance references to Modules 2, 3, and 4 are unchanged
  throughout.

### Phase 1 amendments

- **A1.1 The lock is universal.** `scripts/regen_lock.sh` passes
  `--universal --python-version 3.14` instead of `-p 3.14`. The lock is
  then valid on the grader's machine, the Linux CI runner, and Windows, not
  only the machine that generated it. It has 70 entries rather than the
  spike's 59. The extras are Windows-only packages behind platform markers
  (`colorama`, `tzdata`, `cffi`, `pycparser`) and `packaging` (A1.2).
- **A1.2 `packaging` is a declared dev dependency.** `tests/test_packaging.py`
  imports it directly to parse requirements, so it is listed in the `dev`
  extra rather than relied on as a transitive package. Two tests the plan did
  not name were added: `test_setup_py_declares_every_src_module` and
  `test_lock_satisfies_setup_py_ranges`.
- **A1.3 The fresh-install check can test the working tree.** The gate runs
  before the phase commit exists, so `scripts/fresh_install_check.sh
  --worktree` tests the tree about to be committed. With no argument it tests
  `HEAD`, which is what Phase 11 uses. It copies `module_5` out with
  `git archive` rather than `git clone`. The content is the same, and nothing
  untracked or ignored comes along.
- **A1.4 Coverage is off in the fresh-install test run.** The plan's
  `pytest -m "not db and not integration"` deselects the database tests, which
  are what cover the remaining lines, so the 100% gate would fail it. That run
  passes `--no-cov`. The full gate still enforces 100%.
- **A1.5 Build output is ignored.** The editable install writes
  `src/gradcafe_analytics.egg-info/`, so `*.egg-info/` and `build/` are in
  `.gitignore`.

- **A1.6 Two bugs in `gate.sh` were found and fixed during the Phase 1 log
  step.** The Gate Log row check matched any table row beginning `| 1 |`,
  including the Pylint message counts earlier in `PLAN.md`, so it could report
  a phase as logged when it was not. It now searches only from the
  `## 11. Gate Log` heading on. The heading marker skipped headings that end
  in a closing parenthesis, such as `(CHG-01, CHG-02)`, and it ran after the
  row was appended, so a failure left a row without its `(COMPLETE)` mark. It
  now marks the heading first. Neither bug affected a recorded result: Phase 0
  was logged correctly, and the Phase 1 row was written by the fixed script.
- **A1.7 The gate's own checkers have tests.** `tests/test_gate_checkers.py`
  (marker `security`) feeds `check_secrets.py`, `check_change_register.py`, and
  the `gate.sh log` step inputs they must reject, built in temporary
  directories, and pairs each with an input they must accept. The scripts sit
  outside `src/`, so coverage cannot notice a loosened regex. Each test was
  checked against a deliberately broken copy of the script it covers, and
  against the buggy `gate.sh` from A1.6, to confirm it fails. No Change
  Register row is needed, since this is tooling and not a change to Module 4
  behavior.

### Phase 2 amendments

- **A2.1 `.env.example` and the entry check.** The plan's entry check says a
  local `.env` is "built from `.env.example`", but `.env.example` is a task of
  this phase. The local `.env` was migrated by hand instead: the five `PG*`
  keys were renamed to `DB_*` with their values unchanged, and a
  `TEST_DATABASE_URL` line was added. Values were never printed or committed.
- **A2.2 The example database is `gradcafedb`.** The plan's `.env.example` says
  `DB_NAME=gradcafe`. The database Module 3 and 4 used, and this README's
  setup section, is `gradcafedb`, so the example matches it.
- **A2.3 `TEST_DATABASE_URL` was pulled forward from Phase 5, on purpose.**
  CHG-13 introduces it in Phase 5. This phase's secrets check retires the
  `postgres:postgres@localhost` fallback that `tests/conftest.py` carried from
  Module 4, so tests needed an environment-only source for the test database
  now. `db_url` returns `TEST_DATABASE_URL` and has no default. When it is
  unset, offline tests get a URL naming no user or password at an unreachable
  port, so they cannot find a real database, and `clean_db` fails with a
  message naming the variable. Phase 5 adds `TEST_ADMIN_DATABASE_URL` and the
  app/owner split on top of this, so CHG-13 becomes a split and not an
  introduction.
- **A2.4 `tests.yml` keeps its `PG*` variables.** Task 4 says to remove every
  `PG*` reference from CI. `.github/workflows/tests.yml` runs Module 4, is
  required to stay untouched, and `module_4/` still reads `PG*`, so it
  is correct as it is. Module 5's workflow, `ci.yml` in Phase 9, is written
  without them.
- **A2.5 The retired variable names are assembled from parts in tests.** The
  exit check is a literal `grep` for them across `src/` and `tests/`, and tests
  that prove they are gone have to name them. Building the names at runtime
  keeps the grep literal and meaningful.
- **A2.6 Stale paths in `src/` docstrings.** Five files still said
  `Usage (from module_4/)`, and `pull_data.py` had a comment about `module_4/`.
  These are paths, not provenance, so they now say `module_5/`.
- **A2.7 Documentation.** `docs/overview.rst`, `docs/operations.rst`,
  `docs/testing.rst`, and the README's "Connection settings" section now
  describe `DB_*`. The README's Module 4 history sections, including "Changes to
  carried-over code", are left as the record of Module 4 and are rewritten in
  Phase 10.

- **A2.8 First pass on this README.** Requested during the Phase 2 review. It
  adds the Module 5 header, a status note, a deliverables checklist built from
  the assignment's own list (ticked only where the file exists), a Module 5
  overview and repository structure, Fresh Install for pip and uv, an
  environment-variable table, and the security-tooling commands, with each
  pending item marked. The rest of the README, from "Architecture" onward,
  still describes the Module 4 baseline until Phase 10.

### Phase 3 amendments

- **A3.1 The plan contradicted itself on the limit's digit cap.** Section 7
  says `parse_limit` accepts "at most 6 digits", but the Phase 4 matrix requires
  `limit=1000000`, which has seven, to return 200 and clamp to 100. The matrix
  is the behavior a client sees, so the cap is **9 digits**: `1000000` clamps,
  ten digits and longer are rejected, and `int()` never sees a long string.
- **A3.2 The guard allows psycopg's own `.format()`.** The AST guard exempts
  `.format()` called on a `sql.SQL(...)` literal, which is the composition API
  and quotes what it inserts. It still flags `.format()` on a plain string, and
  it inspects only literal operands of `+` and `%`, so joining two
  `sql.SQL` objects is allowed.
- **A3.3 `execute_query` refuses a bare string.** This enforces rule 1 at the
  one executor. Two test helpers that passed strings now pass `sql.SQL`.
- **A3.4 Constants are parameters, except the formula's numbers.** Including the
  `CASE` labels, which are cast with `CAST(... AS TEXT)` so PostgreSQL need not
  infer a bare parameter's type. `100.0` and `0` stay literal, since they are
  arithmetic and not data.
- **A3.5 Snapshots.** The parity test seeds the full 30,000 rows (A0.4). The
  rendered SQL of the builders is pinned in `tests/snapshots/m5_query_sql.txt`.

### Phase 4 amendments

- **A4.1 The matrix is covered and then some.** Each row of the plan's
  malicious-input table is a parametrized case in `tests/test_sqli_malicious.py`,
  and the file adds cases for every whitelisted sort column, case-insensitive
  and combined filters, ordering, ISO dates, and right-to-left text.
- **A4.2 `SearchFilters` holds its text filters in one mapping.** Seven
  separate fields exceeded Pylint's attribute limit, and decision D6 rules out a
  disable or a relaxed config, so `term`, `status`, `degree`, `nationality` and
  `q` live in a read-only `text` mapping. A filter that was absent or empty is
  simply not in it.
- **A4.3 The LIKE escape character is a bound parameter,** not a literal in the
  SQL text, so the statement still contains no quote character.
- **A4.4 The projection leaves out `comments`.** The plan said "a fixed
  projection" without listing it. Free-text comments are the one column a client
  could use to bulk-read user-written text, and no sort or filter needs them.
- **A4.5 `requested_limit` is echoed only after it passes the digits-only
  check,** so reporting it cannot reflect hostile text.
- **A4.6 The live spot-checks ran read-only against the real local database.**
  `limit=1000000` returned `200` with `limit` 100 and `clamped` true,
  `term=' OR '1'='1` returned `200` with no rows, and `sort=gpa; DROP TABLE
  applicants` returned `400`. The table still held all 30,019 rows afterwards.
- **A4.7 A known gap, closed in Phase 6.** Only an unreachable database is
  mapped to `503`. Any other database error, such as a privilege error, would be
  a bare `500` until CHG-10 adds a JSON error handler.
- **A4.8 The Phase 3 guard tests now cover the search.** The spy proves
  `search_applicants` hands the driver a composable, and the limit check covers
  the search statement under hostile limits.

### Phase 6 amendments, decided in advance

- **A6.1 Compiled-SQL check allows exactly the Phase 3 LIMIT.** Phase 3
  adds a LIMIT to every ORM statement, so the compiled SQL can no longer equal
  the Phase 0 snapshot. Phase 6's `test_compiled_sql_unchanged` therefore
  checks every `*_stmt()` builder against the Phase 0 snapshot with one
  allowance. The compiled text must be the snapshot text plus exactly one
  trailing `LIMIT` clause. The bound parameters must be the snapshot's plus
  that one limit value. The snapshot is never re-captured, so the test still
  shows that the LIMIT is the only change.

## Deliverables checklist

From the assignment's "Final Deliverables" and its expected directory
structure. A box is ticked only when the item exists in the repository now;
the rest name the phase that produces them.

- [x] **`module_5/` carried over from Module 4**, the working application and
      its tests, with Module 4 itself left untouched.
- [x] **`setup.py`** (Phase 1), [setup.py](setup.py): flat modules, runtime
      dependencies, and a `dev` extra.
- [x] **`requirements.txt`** (Phase 1), [requirements.txt](requirements.txt):
      a fully pinned lock of 70 packages including `pylint` and `pydeps`,
      generated from `setup.py` by `scripts/regen_lock.sh`.
- [x] **`.env.example`** (Phase 2), [.env.example](.env.example), with `.env`
      gitignored.
- [x] **`pytest.ini`**, [pytest.ini](pytest.ini).
- [x] **Fresh install by pip and by uv** (Phase 1), proved by
      `scripts/fresh_install_check.sh`; see [Fresh Install](#fresh-install).
- [x] **SQL injection defenses** (Phases 3 and 4): composed SQL, bound
      parameters, construction separated from execution; see
      [CHG-05](#chg-05) and [CHG-08](#chg-08).
- [x] **`LIMIT` on every query, with an enforced maximum** (Phases 3 and 4);
      see [CHG-07](#chg-07).
- [ ] **Least-privilege database role** (Phase 5), with `privileges.png`.
- [ ] **10/10 Pylint evidence**, `pylint_report.txt` (Phase 6). The command is
      documented under [Security tooling](#security-tooling).
- [ ] **`dependency.svg`** (Phase 7).
- [ ] **`snyk-analysis.png`**, and for extra credit `snyk-code-analysis.png`
      (Phase 8).
- [ ] **`.github/workflows/ci.yml`** and **`actions_success.png`** (Phase 9).
- [ ] **`coverage_summary.txt`**: the committed file is still Module 4's
      (102 tests); it is regenerated in Phase 10.
- [ ] **`module_5_report.pdf`** (Phase 10).
- [ ] **Canvas zip and GitHub push, matching** (Phase 11).

## Overview

This module hardens the Grad Café analytics service built in Module 3 and
tested in Module 4. The application is unchanged in purpose: it loads scraped
applicant data into PostgreSQL, analyzes it with raw SQL and the SQLAlchemy
ORM, and serves an analysis page that can pull newly posted entries on demand.
Module 5 adds software assurance around it: the code is packaged and its
environment pinned, credentials come only from the environment, SQL is
composed and parameterized, reads are bounded, the database account is
least-privilege, and static analysis, a dependency graph, and a supply-chain
scan run in CI.

| Area | What Module 5 does | Where | Status |
| --- | --- | --- | --- |
| Packaging | `setup.py` with flat modules; editable install | `setup.py` | done |
| Reproducible environment | pinned lock, installs with pip and uv | `requirements.txt`, `scripts/` | done |
| Secrets | `DB_*` variables, `.env.example`, sanitized connection errors | `src/load_data.py`, `.env.example` | done |
| SQL injection defenses | composed, parameterized SQL, built apart from execution | `src/query_data.py`, `src/load_data.py`, `src/applicant_search.py` | done |
| `LIMIT` enforcement | every query bounded, one definition of the maximum, clamped 1 to 100 | `src/db_safety.py` | done |
| Searchable endpoint | `GET /api/applicants` | `src/applicant_search.py` | done |
| Least privilege | owner and runtime roles | `sql/` | pending |
| Pylint 10.00/10 | fixes in code, no inline disables | `src/` | pending |
| Dependency graph | pydeps and Graphviz | `dependency.svg` | pending |
| Snyk | dependency and code scans | `snyk-analysis.png` | pending |
| CI | lint, graph, Snyk, and tests as four jobs | `.github/workflows/ci.yml` | pending |

Every change made to the Module 4 code, and why, is recorded in the
[Change Register](CHANGES.md) and explained under
[Changes from Module 4](#changes-from-module-4). Changes Module 4 made to the
Module 3 code are described under
[Changes to carried-over code](#changes-to-carried-over-code).

## Repository structure

```text
module_5/
├── src/                        application code, flat modules
│   ├── app.py                  Flask factory, analysis page, button routes
│   ├── pull_data.py            pull orchestration and its injection seams
│   ├── scrape.py               Grad Café page fetching (Module 2)
│   ├── clean.py                page parsing into records (Module 2)
│   ├── load_data.py            connection settings, schema, and loader
│   ├── models.py               SQLAlchemy Applicant model and session factory
│   ├── query_data.py           raw SQL analyses and the output formatters
│   ├── orm_queries.py          the same analyses through the ORM
│   ├── db_safety.py            query limits and input checks
│   ├── applicant_search.py     GET /api/applicants search
│   ├── templates/index.html    the analysis page
│   └── static/style.css        page styles
├── tests/                      all test code; conftest.py holds the fixtures
│   ├── snapshots/              Module 4 answers and compiled SQL, for parity tests
│   ├── test_applicant_search.py    the endpoint's contract and validation
│   ├── test_sqli_malicious.py  the malicious-input matrix, against a real database
│   ├── test_db_safety.py       limit clamping and input validation
│   ├── test_sql_guard.py       no string-built SQL, composed-only, every SELECT limited
│   ├── test_config.py          configuration and secrets handling
│   ├── test_packaging.py       packaging and the lock
│   ├── test_lint_policy.py     every test carries a marker
│   ├── test_gate_checkers.py   the gate's own checkers
│   └── test_*.py               the Module 4 suite, updated
├── scripts/                    gate.sh, change-register and secrets checks,
│                               lock regeneration, fresh-install check
├── docs/                       Sphinx project
├── data/                       bulk JSON input, never imported
├── llm_hosting/                instructor-provided LLM standardizer
├── setup.py                    packaging and dependency source of truth
├── requirements.txt            pinned lock generated from setup.py
├── .env.example                every environment variable, placeholders only
├── pytest.ini                  markers, strict markers, the coverage gate
├── CHANGES.md                  the Change Register
├── PLAN.md                     the execution plan and Gate Log
└── README.md
```

`src/` modules import each other flatly (`from models import ...`). They
resolve through the editable install of `setup.py` (see
[CHG-01](#chg-01)); `src/` is deliberately not a package, because converting it
would break parity with Module 3, where these files sat at the top level.

Not yet present, and produced in later phases: `sql/` (role and grant
scripts), `dependency.svg`, `snyk-analysis.png`, `pylint_report.txt`,
`.pylintrc` content beyond the source root, `privileges.png`,
`actions_success.png`, `module_5_report.pdf`, and
`../.github/workflows/ci.yml`.

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

Copy `.env.example` to `.env` and fill it in. `.env` is gitignored, and
`python-dotenv` loads it from `module_5/` if it exists; variables already set
in the shell take precedence. Both the psycopg code and the ORM read:

```bash
DB_HOST=localhost
DB_PORT=5432
DB_NAME=gradcafedb
DB_USER=gradcafe_app          # runtime account: the web app and Pull Data
DB_PASSWORD=change-me
# DB_OWNER_USER / DB_OWNER_PASSWORD: schema setup and bulk load only
```

`DATABASE_URL` is an optional single-URL override, used by CI and tests. It
takes precedence over `DB_*`. The test suite reads `TEST_DATABASE_URL`, a
disposable database it truncates. The `PG*` variables Module 3 used are no
longer read; see [CHG-03](#chg-03).

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

### Environment variables

Every variable the code reads, all set in `.env` (see `.env.example`) or the
shell. A missing required variable raises an error that names the variable and
never shows a value.

| Variable | Used by | Required | Meaning |
| --- | --- | --- | --- |
| `DB_HOST` | every role | yes, unless `DATABASE_URL` is set | PostgreSQL host |
| `DB_PORT` | every role | yes, unless `DATABASE_URL` is set | PostgreSQL port |
| `DB_NAME` | every role | yes, unless `DATABASE_URL` is set | database name |
| `DB_USER`, `DB_PASSWORD` | the `app` role: web app, Pull Data, ORM | yes, unless `DATABASE_URL` is set | runtime account |
| `DB_OWNER_USER`, `DB_OWNER_PASSWORD` | the `owner` role: schema setup and bulk load | only for the owner role | owner account; keep out of the running app's environment |
| `DATABASE_URL` | every role | no | single-URL override; beats `DB_*`, loses to an explicit argument |
| `TEST_DATABASE_URL` | the test suite | for `db` and `integration` tests | disposable database the tests truncate |
| `PORT` | `src/app.py` | no | port for the development server (default 8080) |

All are read in `src/load_data.py` (`get_db_config`), `src/models.py`
(`build_url`), and `tests/conftest.py`. The owner role is wired up with the
least-privilege database in Phase 5; until then the runtime variables name the
account you already use.

### Fresh Install

One environment covers the application, the ETL code, the test suite with
coverage, linting, the dependency graph, and the Sphinx build. Dependencies are
declared once, in `setup.py`; `requirements.txt` is the pinned lock generated
from it. Python 3.14 is required (3.14.6 is what the project is developed and
tested on). From a fresh clone, either way works:

**pip**

```bash
cd module_5
python3.14 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e . --no-deps
```

**uv**

```bash
cd module_5
uv venv -p 3.14 .venv
source .venv/bin/activate
uv pip sync requirements.txt
uv pip install -e . --no-deps
```

The second line of each recipe is the editable install of the project itself.
It is what lets the flat `src/` modules import each other from anywhere, and it
is the only supported way to install the project: a plain `pip install .` would
not carry `src/templates/` and `src/static/`, because flat modules have no
package to hold package data. See [CHG-01](#chg-01) and [CHG-02](#chg-02).

`scripts/fresh_install_check.sh` proves both recipes. It copies the committed
tree into a temporary directory with no `.venv` and no `.env`, runs each recipe
there, imports every module from outside `src/`, runs `pylint --version` and
`pydeps --version`, and runs the offline tests. To add or change a dependency,
edit `setup.py` and run `scripts/regen_lock.sh`; do not edit the lock by hand.

The project targets Python 3.14. Module 4's CI workflow pins 3.14.6 exactly
(Module 5's workflow follows in Phase 9), and Read the Docs offers major.minor
only, so it pins 3.14.

### LLM standardizer setup

The standardizer keeps its own environment, as in Module 2, because it depends
on `llama-cpp-python`, which compiles native code. Pull Data runs it in that
environment.

```bash
cd module_5/llm_hosting
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

All commands run from `module_5/` with the main environment active.

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

## Security tooling

The commands are fixed here so that a reader can reproduce each result. All run
from `module_5/` with the environment from [Fresh Install](#fresh-install)
active.

| Tool | Command | Reads as | Status |
| --- | --- | --- | --- |
| Pylint | `pylint --rcfile=.pylintrc --fail-under=10 src` | must print `rated at 10.00/10` with no message lines | pending (Phase 6); currently 8.31/10 |
| pydeps | `pydeps src/app.py --noshow -T svg -o dependency.svg` | needs Graphviz's `dot` on the path | pending (Phase 7) |
| Snyk, dependencies | `snyk test --file=requirements.txt --package-manager=pip --command=python` | lists known vulnerabilities in the pinned packages | pending (Phase 8) |
| Snyk Code | `snyk code test` | static analysis of `src/` (extra credit) | pending (Phase 8) |

Pylint is run on `src/` only, as the assignment requires, and the project
carries no inline `# pylint: disable`; findings are fixed in the code. The one
configuration file, `.pylintrc`, says where the source lives and relaxes no
rule.

Two scripts guard the repository itself: `scripts/check_secrets.py` fails if a
credential-shaped literal appears in `src/` or `tests/`, and
`scripts/gate.sh` runs the checks above together with the tests before a phase
may be committed.

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

*Module 4 history. Module 5 removed the `PG*` fallbacks; see [CHG-03](#chg-03).*

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

The full suite runs from `module_5/`, because `pytest.ini` scopes coverage to
`src/` relative to itself. Module 5 runs every collected test, with no marker
expression (see [CHG-18](#chg-18)):

```bash
cd module_5
pytest
```

The `db` and `integration` tests need `TEST_DATABASE_URL` to name a disposable
database; the rest run with no database at all. *The marker table, counts, and
coverage output below are Module 4's, and are regenerated in Phase 10.*

Every test carries at least one marker; unmarked tests are not permitted.
`pytest.ini`'s marker text is the assignment's own required wording, quoted
exactly:

| Marker | `pytest.ini` text |
| --- | --- |
| `web` | Flask route/page tests |
| `buttons` | "Pull Data" and "Update Analysis" behavior |
| `analysis` | formatting/rounding of analysis output |
| `db` | database schema/inserts/selects |
| `integration` | end-to-end flows |

### Two application fixtures

Tests reach the application only through `create_app()`, via two fixtures in
`conftest.py` that fake different amounts of it:

| Fixture | scraper | loader | query | Needs PostgreSQL |
| --- | --- | --- | --- | --- |
| `app` / `client` | fake | fake (records calls, writes nothing) | fake | No |
| `db_client` | fake | real, against a truncated test database | real, same database | Yes |

`app`/`client` serves `web`, `buttons`, and `analysis` tests. Faking `query`
as well as the scraper and loader is what keeps `POST /update-analysis` from
reaching PostgreSQL even when a pull is not in progress: without it, only
`web` and `analysis` would be database-free, since `buttons` tests call that
route too. Measured: all 24 `web`/`buttons`/`analysis` tests run in 0.05s with
no `DATABASE_URL` set at all. `db_client` serves `db` and `integration`
tests, against a disposable database `clean_db` truncates before and after
each test; its scraper is still faked, so even these tests never reach Grad
Café, but its loader and queries are real, which is what lets a test assert
on actual rows.

### Why the scraper is faked at two different depths

`test_buttons.py` fakes the whole `scraper` callable at the `create_app()`
boundary, which is what the assignment itself asks for ("Triggers the loader
with the rows from the scraper (should be faked / mocked)"). That tests the
route's contract: status codes, the JSON shape, busy gating. It does not
exercise what Pull Data's scraper actually does when it runs, because the
real `pull_data.scrape_new_records()` is never called.

`test_pull_pipeline.py` closes that gap, also marked `buttons` per the table
above (its definition is "Pull Data" behavior, not "button endpoint"
behavior, so testing the pipeline one level below the route fits it). It
calls the real `scrape_new_records()`, with a fake Selenium driver and a fake
LLM subprocess standing in for the two outward dependencies, and proves the
real logic: stopping at the database's newest entry across multiple pages of
results, filtering out entries already present, and each of Pull Data's error
paths (empty database, Grad Café unreachable, no new entries, the
standardizer's environment missing). `clean.py`'s HTML parsing is exercised
directly against small crafted pages, no fakes needed at all, since it is
pure parsing with no outward dependency to replace.

Writing these tests needed two more injection seams in `pull_data.py`, added
to dependencies that were already there rather than new ones:

- `fetch_html`, because `scrape._fetch_html()` drives a real Selenium
  `WebDriverWait`. A test for "the page never arrived" routed through the
  real function would block for its full 30-second timeout; `fetch_html` can
  answer instantly instead, without touching what `browser_factory` means.
- `scrape_new_records()`'s `sleep` argument, which it previously dropped
  rather than passing to `_scrape_new_pages()`. A genuine two-page pagination
  test needs two pages, which otherwise means one real `PAGE_DELAY` (2
  seconds) in the middle of a test suite that is supposed to run in seconds,
  not minutes.

### The five files beyond the required five

`pytest.ini` sets `--cov-fail-under=100` against all of `src/`, not only the
code the five required files reach, and two facts about Module 3's own
design are what make that gap real rather than theoretical:

- **Two independent paths to the same nine questions.** Module 3 built
  `query_data.py` (raw SQL) and `orm_queries.py` (the ORM) side by side, and
  wired only the ORM path into the Flask page. `query_data.py` still ships in
  `src/` for its own command line (`python3 src/query_data.py`); the app
  never calls it, and no test aimed at app _behavior_ ever would either.
- **Command-line entry points nothing in the web app reaches.** `main()` in
  every module, `models.py`'s `_verify_mapping()`, and `scrape.py`'s
  `scrape_data()` (the one-time historical batch scraper that produced the
  original 30,000-row dataset, superseded for ongoing use by Pull Data's
  incremental pull in `pull_data.py` but still present in `src/`) are each
  reachable only by calling the function directly, not by posting to a route
  or faking the scraper at the `create_app()` boundary.

Five more files close what the five required ones leave dark because of
those two facts, each for a specific, named reason rather than to pad the
number:

| File | Marker | Why it exists |
| --- | --- | --- |
| `test_pull_pipeline.py` | `buttons` | see above: the scraper's real orchestration and `clean.py`'s HTML parsing |
| `test_scrape.py` | `buttons` | `scrape_data()`, the Module 2 batch scraper the Pull Data button never calls but `src/` still contains; gained the same `browser_factory`/`fetch_html`/`sleep` seams as `pull_data.py`, for the same reason |
| `test_query_data.py` | `db` | the raw-SQL analyses, a second, independent path to the same questions that `app.py` never reads; run against a real database rather than a fake cursor, so the SQL text itself is proven, not just the Python that unpacks it |
| `test_orm_queries.py` | `db` | the `--sql` debug output and `main()`, which `app.py`'s use of the same functions never reaches |
| `test_models.py` | `db` | the module-level, cache-for-the-process `get_engine()`/`get_session()` the command-line scripts use, and `_verify_mapping()`, which doubles as a genuine proof the `Applicant` model still matches the live schema |

Coverage, from `coverage_summary.txt`:

```text
Name                 Stmts   Miss  Cover
-----------------------------------------
src/app.py             114      0   100%
src/clean.py            91      0   100%
src/load_data.py       110      0   100%
src/models.py           64      0   100%
src/orm_queries.py     118      0   100%
src/pull_data.py       116      0   100%
src/query_data.py       82      0   100%
src/scrape.py          107      0   100%
-----------------------------------------
TOTAL                  802      0   100%
102 passed in 0.79s
```

Nine `# pragma: no cover` lines across `src/`, each with a one-line reason
beside it: one per module's `if __name__ == "__main__":` block, and one
branch in `scrape._fetch_html()` that a real Selenium timeout or standing in
for `WebDriverWait`'s own internal sleep are the only ways to reach.

## Documentation

Published at <https://jhu-software-concepts-5thlegionnaire.readthedocs.io/en/latest/>.

The Sphinx project lives in `docs/`. To build it locally:

```bash
cd module_5
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

## Development process

Module 4 was built spec-driven rather than file-by-file: `PLAN.md`, in this
same directory, is the living plan, not a one-time proposal. It lays out
five phases (0 through 4, matching the sections above) _before_ any of
them were built, then each phase's section was rewritten afterward to say
what was actually built, including the three places execution diverged from
the plan and why: `runner` as a seam separate from `scraper`/`loader`
(Phase 0), two application fixtures instead of one because no single fixture
could serve both halves of the suite (Phase 1), and the scraper
orchestration having zero test coverage despite `test_buttons.py` doing
exactly what the assignment asked of it (also Phase 1, caught mid-review).
Every phase ended with a working, tested, committed state before the next
began, and every commit in this module's history corresponds to one of
those boundaries.

This module also moved to consistent use of Claude Code, the terminal-based
tool, for the whole of the work, rather than the mix of Claude's desktop and
web apps used on earlier modules. The practical effect was a single
continuous session with direct access to the repository, the test runner,
and a live PostgreSQL connection throughout: every claim in this README
about test counts, coverage percentages, and build output was run and
checked in that session, not written from memory or assumption. `PLAN.md`
is the record of that; this README is the summary of it.
