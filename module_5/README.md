# EN 605.256 Modern Software Concepts in Python: Module 5

**Name:** Joshua Latz | **JHED ID:** jlatz1 | **Module 5:** Software Assurance and Secure SQL (SQLi Defense)
**Repository:** `git@github.com:5th-legionnaire/jhu_software_concepts.git`, this work under `module_5/`
**Python:** 3.14.6 | **PostgreSQL:** 18.6 local, 16 in CI | **Baseline:** `module_4` at commit `1ecf2c9`
**Documentation:** <https://jhu-software-concepts-5thlegionnaire.readthedocs.io/en/latest/> (serves Module 4 until
the end of Module 5, when it is repointed here; Module 4 stays reachable at the `module-4-final` tag)

This module hardens the Grad Café analytics service from Modules 3 and 4: it loads scraped applicant data into
PostgreSQL, analyzes it with raw SQL and the SQLAlchemy ORM, and serves an analysis page and a JSON search endpoint.
Module 5 adds packaging and a pinned environment, credentials from the environment only, composed and
parameterized SQL, bounded reads, a least-privilege database account, 10.00/10 Pylint, a dependency graph,
Snyk scans, and a four-job CI pipeline. Every design change from Module 4 is in the
[Change Register](CHANGES.md) with its reason and the tests that verify it.

## Start here: verify the submission

Each row is one thing the assignment asks for, where it is, and one command that checks it from `module_5/` once
[the environment is up](#get-it-running).

| Requirement | Evidence | Check it |
| --- | --- | --- |
| Pylint 10.00/10 on `src/`, no inline disables | [pylint_report.txt](pylint_report.txt), [.pylintrc](.pylintrc) | `pylint --rcfile=.pylintrc --fail-under=10 src` |
| Tests, 100% coverage, every test marked | [coverage_summary.txt](coverage_summary.txt) | `pytest` (605 tests) |
| No SQL built from strings; composed and parameterized; construction apart from execution | [tests/test_sql_guard.py](tests/test_sql_guard.py), [CHG-05](#chg-05) | `pytest tests/test_sql_guard.py` |
| Malicious input handled (51 cases, never a 500) | [tests/test_sqli_malicious.py](tests/test_sqli_malicious.py), [CHG-08](#chg-08) | `pytest tests/test_sqli_malicious.py` |
| `LIMIT` on every query, maximum enforced | [src/db_safety.py](src/db_safety.py), [CHG-07](#chg-07) | `pytest tests/test_db_safety.py` |
| Credentials from the environment, `.env.example`, `.env` ignored | [.env.example](.env.example), [leak check](#credentials-were-checked-for-leaks) | `python scripts/check_credential_leaks.py` |
| Least-privilege database account | [sql/](sql/), [privileges.txt](privileges.txt), [privileges.png](privileges.png), [CHG-12](#chg-12) | `pytest tests/test_least_privilege.py` |
| Dependency graph and its explanation | [dependency.svg](dependency.svg), [report/dependency_summary.md](report/dependency_summary.md) | `pydeps src/app.py --noshow -T svg -o dependency.svg --max-module-depth=1` |
| `setup.py`, pinned `requirements.txt`, pip and uv installs | [setup.py](setup.py), [requirements.txt](requirements.txt) | `scripts/fresh_install_check.sh` |
| Snyk, findings fixed (extra credit: Snyk Code) | [snyk_report.json](snyk_report.json), [snyk-analysis.png](snyk-analysis.png), [snyk-code-analysis.png](snyk-code-analysis.png), [triage](report/snyk_triage.md) | `scripts/snyk_scan.sh` |
| GitHub Actions CI, four jobs | [.github/workflows/ci.yml](../.github/workflows/ci.yml), [actions_success.png](actions_success.png) | the [Actions page](https://github.com/5th-legionnaire/jhu_software_concepts/actions/workflows/ci.yml) |
| PDF report | [module_5_report.pdf](module_5_report.pdf), built by [report/build_report.py](report/build_report.py) | `python report/build_report.py` |
| Every change from Module 4, explained and tested | [CHANGES.md](CHANGES.md), [Changes from Module 4](#changes-from-module-4) | `python scripts/check_change_register.py 9` |
| Process: gated phases, Gate Log | [PLAN.md](PLAN.md), [Development process](#development-process) | `scripts/gate.sh 9` |

**Results at a glance** (each produced by running the command, not typed): 605 tests passed, 100.00% coverage,
Pylint 10.00/10, Snyk 0 findings across all 70 pinned packages (22 found and fixed), 51 malicious-input cases, and
phases 0 to 8 recorded in the Gate Log with their commit, test count and score.

**Status.** Phases 0 to 9 are complete and gated. CI run
[37408248003](https://github.com/5th-legionnaire/jhu_software_concepts/actions/runs/37408248003) on commit `669064d` is
green in all five jobs (`lint`, `dependency-graph`, `snyk`, `test (pip)`, `test (uv)`), shown in
[actions_success.png](actions_success.png). The report is [module_5_report.pdf](module_5_report.pdf). What remains is
after submission: repointing Read the Docs to this module (Phase 11, with Module 4 kept at the `module-4-final` tag).
Limitations of the data and the application are under [Known issues](#known-issues).

## Get it running

Python 3.14 is required (3.14.6 is what this was built and tested on). Everything below runs from `module_5/`.

### 1. Environment: Fresh Install (pip or uv)

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

### 2. Configuration: connection settings

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

### 3. PostgreSQL

Install PostgreSQL, then create two empty databases: the one the application uses, and a disposable one the tests
truncate and must never be pointed at real data.

```bash
createdb gradcafedb
createdb gradcafe_test
```

The next section creates the two least-privilege accounts and loads the schema.


### Database setup

Run once, as a PostgreSQL superuser, from `module_5/`. `OWNER_PW` and `APP_PW`
are passwords you choose; they go into `.env` and nowhere else. The scripts
never receive a password. Each one is first turned into a SCRAM-SHA-256
verifier, which PostgreSQL stores as it is, and handed over in the
environment. A password on a `psql` command line shows in the process list, and
one inside a statement is written to the server log if the statement fails, so
neither is used. See [Credentials were checked for leaks](#credentials-were-checked-for-leaks).

```bash
# 1. The two roles, and a database only they can connect to
export OWNER_VERIFIER=$(printf %s "$OWNER_PW" | python3 scripts/scram_verifier.py)
export APP_VERIFIER=$(printf %s "$APP_PW" | python3 scripts/scram_verifier.py)
psql -d postgres -v db=gradcafedb -f sql/roles.sql

# 2a. A new database: the owner creates the table and loads the data
DB_OWNER_USER=gradcafe_owner DB_OWNER_PASSWORD="$OWNER_PW" python3 src/load_data.py
psql -d gradcafedb -f sql/grants.sql

# 2b. An existing database: move the table under the owner instead
psql -d gradcafedb -f sql/migrate_ownership.sql
```

Then set `DB_USER=gradcafe_app` and `DB_PASSWORD` in `.env`. Leave the owner's
credentials out of it, and give them to the loader only for the moment you run
it, as above. For the test database, repeat step 1 with `-v db=gradcafe_test`,
create the table as the owner, apply `sql/grants.sql`, and set
`TEST_DATABASE_URL` and `TEST_ADMIN_DATABASE_URL`. See [CHG-12](#chg-12) for
what each account may do and why.

### Credentials were checked for leaks

**Why this section exists.** Phase 5 creates real accounts with real
passwords, and a security control that is only asserted is an unverified claim.
Module 5 is about assurance, which means evidence that a property holds and not
confidence that it should. At the go-ahead for the live setup, the instruction
was to make sure no credential was being logged, to test that it was not, and to
document that the check was done. That instruction is the reason for everything
below. It also found two leaks the original plan would have produced, which is
the argument for checking: they were invisible until someone looked at the
server's own settings.

A password can leak by more routes than a committed file, so the setup was
designed around four of them and then checked directly, with the real values,
rather than assumed safe.

| Route | What would have happened | What is done instead |
| --- | --- | --- |
| The process list | `psql -v owner_pw=...` puts the password on a command line any local user can read | Passwords are never arguments. `roles.sql` reads them from the environment, and `scram_verifier.py` reads one from standard input |
| The server log | PostgreSQL writes the text of a statement that **fails** to its log (`log_min_error_statement` is `error` here), and this install's log file is readable by every local user, so a failed `ALTER ROLE ... PASSWORD 'secret'` would have published the password | The statement carries a SCRAM-SHA-256 verifier, a salted hash that PostgreSQL stores unchanged. The cleartext never reaches the server |
| Shell and psql history | A password typed into a command is recorded in `~/.zsh_history` or `~/.psql_history` | The passwords were generated in memory, never typed, and never put on a command line |
| Documentation | A README that says `-v owner_pw=...` teaches the leak | A test fails if the setup instructions mention a cleartext password argument |

**Checked, not assumed.** After provisioning, the real passwords were searched
for in the PostgreSQL log, `~/.zsh_history`, `~/.bash_history`, `~/.psql_history`,
every file in the repository, the scratch directory, and everything `psql` and
Python printed during setup: **no match anywhere**. A cleartext login also works
against the stored verifier, which shows the verifier approach is sound and not
a role nobody can log in as.

**Why the check is permanent and not a one-time look.** A one-time search proves
the state of the world at that moment and says nothing about the next commit.
The ways it can regress are ordinary: someone pastes a working command into the
README, a new log line prints a connection string, a CI step echoes the
environment, a debugging session commits a `.env` fragment. None of these needs
anyone to be careless about security, only to be busy. So the check runs on every
gate, where a leak stops the commit, and it searches git history as well as the
tree, because deleting a leaked file does not remove it from the repository. This
is the same idea as the rest of the module: Pylint at 10.00, the SQL guard, and
the least-privilege tests all move a failure to the earliest and cheapest point,
before it ships.

**Checked on every gate from Phase 5 on.** `scripts/check_credential_leaks.py`
reads the passwords out of `.env` and searches the working tree, every commit in
git history (so a leak that was later deleted still fails), the server log, and
the shell history files. It prints counts and labels only, and never a password:
git receives its search patterns from a private temporary file, not an argument.
Its own tests plant a password in a file, a log, and a deleted commit and require
that each is found, and require that the output never contains it. Each of those
tests was also confirmed to fail against a deliberately broken copy of the check.
`scripts/check_secrets.py` additionally scans `sql/` for a password literal.

**What this does not cover.** The cleartext passwords exist in `.env`, which is
gitignored and mode 600, because the application and the test fixtures need
them. The owner's password is in `TEST_ADMIN_DATABASE_URL` for the same reason.
The verifiers sit in PostgreSQL's `pg_authid`, readable only by superusers. A
screen share, a backup of the data directory, or a process that can read another
process's environment is outside what a repository can protect.

### 4. Run it

```bash
python3 src/app.py        # then open http://127.0.0.1:8080/analysis   (set PORT to change 8080)
curl "http://127.0.0.1:8080/api/applicants?limit=5&sort=gpa&order=desc"
```

Command-line programs: `python3 src/query_data.py` (raw SQL results), `python3 src/orm_queries.py` (ORM results),
`python3 src/pull_data.py` (one pull without the page). Loading the bulk data is the owner's job and is in the next
section. Then verify with the [table above](#start-here-verify-the-submission); the quickest full check is `pytest`.

### 5. Optional pieces

#### LLM standardizer setup

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

#### Browser setup for Pull Data

Grad Café sits behind Cloudflare. As in Module 2, the verification must be
cleared once, by hand, in the persistent Chrome profile the scraper uses
(`~/.gradcafe-chrome-profile`).

**No test launches a browser.** `pull_data.py` takes its driver as an injected
argument, so the suite supplies a stand-in instead.

## Security tooling

The commands are fixed here so that a reader can reproduce each result. All run
from `module_5/` with the environment from [Fresh Install](#1-environment-fresh-install-pip-or-uv)
active.

| Tool | Command | Reads as | Status |
| --- | --- | --- | --- |
| Pylint | `pylint --rcfile=.pylintrc --fail-under=10 src` | must print `rated at 10.00/10` with no message lines | **10.00/10**, committed as `pylint_report.txt` (Phase 6) |
| pydeps | `pydeps src/app.py --noshow -T svg -o dependency.svg --max-module-depth=1` | needs Graphviz's `dot` on the path; arrows point from an imported module to its importer | done: [dependency.svg](dependency.svg), explained in [report/dependency_summary.md](report/dependency_summary.md) |
| Snyk, dependencies | `scripts/snyk_scan.sh` (it runs `snyk test --file=requirements.txt --package-manager=pip --command=python` on the pinned lock; see below) | lists known vulnerabilities in the pinned packages; `✔ no vulnerable paths found` is clean | done: 22 findings fixed, 0 remain |
| Snyk Code | `snyk code test src` | static analysis of `src/` (extra credit) | done: 1 LOW accepted, see the triage |

Pylint is run on `src/` only, as the assignment requires, and the project
carries no inline `# pylint: disable`; findings are fixed in the code. The one
configuration file, `.pylintrc`, says where the source lives and relaxes no
rule.

Two scripts guard the repository itself: `scripts/check_secrets.py` fails if a
credential-shaped literal appears in `src/` or `tests/`, and
`scripts/gate.sh` runs the checks above together with the tests before a phase
may be committed.

### Upgrading dependencies when a vulnerability is known

A pinned lock is a snapshot of what was true on the day it was generated. Pinning
is what makes an environment reproducible, and it also freezes whatever flaws that
version has, because advisories are published *after* a release. A lock that was
clean when it was written is not clean forever, which is why the scan is run
against the lock, repeatedly, and not once.

**What the scan found here.** 22 entries, which are 4 distinct issues in 2 of the 70
pinned packages. Snyk lists one entry per dependency path, so `urllib3`'s three
issues appear 21 times.

| Package | Issue | Severity | Why it matters here |
| --- | --- | --- | --- |
| `urllib3` 2.7.0 | Improper Certificate Validation | High | A client could accept a certificate it should reject, which is what lets a machine in the middle impersonate a server |
| `urllib3` 2.7.0 | Allocation of Resources Without Limits or Throttling | High | A hostile response can exhaust memory or CPU, a denial of service |
| `urllib3` 2.7.0 | Infinite loop | Medium | A request can hang a process |
| `python-dotenv` 1.0.1 | Symlink Attack | Medium | Rewriting a `.env` file can be redirected through a symlink to another file |

**What was done, and why it was the right call.** `urllib3` went to 2.8.0 and
`python-dotenv` to 1.2.4, and exactly two lines of the lock changed. Both versions
were already permitted by the compatible-release ranges in `setup.py`, so a
plain reinstall would not have taken them: a lock does not move on its own. The
floors were raised (`urllib3~=2.8`, `python-dotenv~=1.2`) so that regenerating the
lock can never go backward, and a test, `test_remediated_versions_stay_remediated`,
fails if it does. The full suite was then re-run on the new versions, because a
dependency bump is a code change that the tests, not the version number, vouch for.
It passed, and Snyk now reports no findings in any of the 70 packages.

**Why upgrade instead of arguing the flaw is unreachable.** The honest reachability
analysis for each of these is short and not reassuring. `urllib3` is the HTTP client
under Selenium, so it carries the project's browser traffic. `python-dotenv` is
only read here, so its flaw is out of reach, but that conclusion depends on nobody
ever calling its write functions. Deciding whether an advisory applies costs more
than the fix, and is wrong in the direction that matters when it is wrong. A patch
in a version range already allowed costs minutes, and the cost of deferring it grows
with every release that lands on top of it, because the eventual jump gets larger
and riskier. So the rule used here is: when a fixed version exists, take it, prove
it with the tests, and record what was found.

### False positives: refactor the code, even when you know it is safe

Not everything a tool reports is a defect, and this module met several. Pylint's
type inference could not see through `sqlalchemy.func`, so every `func.count()`
reported "not callable", and it read `sessionmaker[Session]` as subscripting
something that is not subscriptable (23 messages in all, CHG-16). Snyk Code
flagged `{"user": "DB_USER", "password": "DB_PASSWORD"}` as a hardcoded password,
when the string is the *name* of an environment variable (CHG-21). This project's
own secrets scanner had the same trouble with the same line. None of these was a
vulnerability, and in each case the code was changed anyway. The reasons are the
point:

- **The investigation recurs; the fix happens once.** Each time a scan runs, a
  reviewer, a teammate, or the same author six months later must re-read the
  finding, re-trace the code, and re-conclude "false positive". That cost is paid on
  every run, for as long as the code exists. Reshaping the code once removes the
  recurring cost, and reshaping it with a test that encodes the pattern (here, an
  AST check that no `"password"` key holds a string literal) means it cannot come
  back unnoticed.
- **A standing red result stops being read.** A scan with a known, accepted finding
  trains everyone to look past red. A clean baseline means a new finding is news, and
  that signal is worth more than the finding was.
- **Suppression hides more than the finding.** An inline `# pylint: disable` or a
  scanner ignore rule silences the line for every future reason as well. A real
  problem that later appears on that line is invisible. That is why this project has
  zero inline disables and a test that fails if one is added (decision D6).
- **If a tool can misread it, so can a person.** A dict that pairs the key
  `"password"` with a string literal does look like a credential at a glance. A pair
  of variable names, `("DB_USER", "DB_PASSWORD")`, says what the code means. The
  refactor was a small clarity improvement as well as a way to quiet a scanner.

**The limit, so this is not mistaken for appeasing tools.** The change must be
behavior-neutral, tested, and an improvement or at worst neutral for the reader. The
same scan raised a LOW path-traversal note on `python3 src/load_data.py <file>`,
and that was *not* refactored away. The path is chosen by the person running the
tool on their own machine, so there is no attacker to defend against, and adding a
meaningless check would be security theater: code that exists to satisfy a scanner,
costs the reader something, and gives false assurance. That finding is documented
as an accepted risk, with the reasoning, in `report/snyk_triage.md`. The test for
whether to change the code is whether the result is better code, not whether the
tool goes quiet.

## CI

`.github/workflows/ci.yml` runs on every push and every pull request, on any branch, and has four jobs that fail
independently so a red check names the requirement that broke ([CHG-19](#chg-19)).

| Job | Enforces |
| --- | --- |
| `lint` | Pylint scores exactly 10.00 on `src/` |
| `dependency-graph` | pydeps and Graphviz build a valid `dependency.svg` (uploaded as an artifact) |
| `snyk` | no dependency finding at or above high across all 70 pinned packages; Snyk Code report-only; skipped with a notice when no token is available |
| `test` | the full suite at 100% coverage on **pip and uv**, against PostgreSQL 16 with the same two least-privilege roles as production |

The first run found three tests that passed locally only because of a developer's `.env`; the suite no longer reads it
([A9.6](#phase-9-amendments)). `actions_success.png` is the screenshot of the green run, and
[`tests/test_ci_config.py`](tests/test_ci_config.py) fails if a gate is removed from the workflow.

## Testing

```bash
pytest                      # the whole suite: 605 tests, coverage gate 100% on src/
```

There is no marker selection: every test runs. Every test carries one of six markers (`web`, `buttons`, `analysis`,
`db`, `integration`, `security`), and a collection hook stops the run if one does not ([CHG-18](#chg-18)). The suite
is hermetic: it never reads your `.env` (only `TEST_DATABASE_URL` and `TEST_ADMIN_DATABASE_URL`, by name), so a local
run sees what CI sees. The `db` and `integration` tests need those two URLs to name a disposable database, as the
runtime and owner accounts; every other test runs with no database at all.

| Test file | What it proves |
| --- | --- |
| `test_sql_guard.py`, `test_db_safety.py` | no SQL built from strings, only composed statements execute, every SELECT has a bounded `LIMIT` |
| `test_sqli_malicious.py`, `test_applicant_search.py` | the search endpoint's contract, and 51 hostile inputs never produce a 500 or change a row |
| `test_least_privilege.py`, `test_database_scripts.py` | the two accounts are what the database says they are; no cleartext password is sent or documented |
| `test_query_data.py`, `test_orm_queries.py` | answers equal Module 4's over all 30,000 rows; the ORM's compiled SQL is Module 4's plus one `LIMIT` |
| `test_config.py`, `test_packaging.py` | configuration precedence and error messages; the lock covers `setup.py` and is fully pinned |
| `test_lint_policy.py`, `test_gate_checkers.py` | `.pylintrc` relaxes nothing; the secrets, register, leak and gate checks reject what they should |
| `test_dependency_graph.py`, `test_snyk_scan.py`, `test_ci_config.py` | the graph is current, the Snyk fixes stay fixed, CI keeps its gates |
| the Module 4 files, updated | Flask page, buttons, formatting, loader, pull pipeline, scraper |

No test touches the internet, launches a browser, runs a real scrape, or calls `sleep()`.

## Architecture

Three layers. The published Sphinx documentation goes further.

**Web layer.** `src/app.py` exposes `create_app(services=None, *, database_url=None, testing=False)`. Every outward
dependency arrives in one frozen `Services` object (`scraper`, `loader`, `query`, `runner`, `search`), each optional
and defaulting to the real implementation ([CHG-09](#chg-09)), so `python3 src/app.py` is unchanged from Module 3 while
a test passes fakes and reaches no network and no database.

| Route | Method | Responses |
| --- | --- | --- |
| `/analysis` (and `/`) | `GET` | `200` the page; `503` the page with an error notice |
| `/pull-data` | `POST` | `200 {"ok": true, "inserted": n}`; `202 {"ok": true, "started": true}`; `409 {"busy": true}`; `500 {"ok": false, "error": ...}` |
| `/update-analysis` | `POST` | `200 {"ok": true, "total": n}`; `409 {"busy": true}`; `503 {"ok": false, "error": ...}` |
| `/api/applicants` | `GET` | `200` rows with the effective `limit`; `400` rejected input; `503` database unreachable; see [CHG-08](#chg-08) |

Any unhandled error answers `500 {"ok": false, "error": ...}` without the exception's text ([CHG-10](#chg-10)). The page
carries `data-testid="pull-data-btn"` and `data-testid="update-analysis-btn"`, and every analysis value is labelled
`Answer:` with percentages to two decimals.

**ETL layer.** `scrape.py` renders Grad Café pages in Chrome, `clean.py` parses them, and `pull_data.py` orchestrates
them, standardizes with the LLM, and hands records to the loader. `pull_data.run_pull(scraper, loader)` is the seam
the route and the tests share.

**Database layer.** `load_data.py` owns settings, schema and insert; `models.py` maps the table for SQLAlchemy;
`query_data.py` and `orm_queries.py` answer the same questions in composed SQL and through the ORM;
`db_safety.py` and `applicant_search.py` hold the limit, input checks and search. The import structure is in
[dependency.svg](dependency.svg).

## Repository structure

```text
module_5/
├── src/                  application code, flat modules (app, applicant_search, clean, db_safety, load_data,
│                         models, orm_queries, pull_data, query_data, scrape), templates/, static/
├── tests/                605 tests; conftest.py holds fixtures and the marker policy; snapshots/ holds the
│                         Module 4 answers and compiled SQL the parity tests compare against
├── sql/                  roles.sql, grants.sql, migrate_ownership.sql
├── scripts/              gate.sh and its checks, snyk_scan.sh, scram_verifier.py, regen_lock.sh,
│                         fresh_install_check.sh, render_query_sql.py, capture_m4_snapshots.py
├── report/               build_report.py (the PDF), dependency_summary.md, snyk_triage.md
├── snyk/                 Snyk scans before the fixes and for the marker-excluded packages
├── docs/                 Sphinx project            data/   llm_extend_applicant_data.json (the loader's input)
├── llm_hosting/          Pull Data's LLM standardizer (its own environment; see above)
├── setup.py  requirements.txt  pytest.ini  .pylintrc  .editorconfig  .env.example
├── CHANGES.md  PLAN.md  README.md
└── evidence: pylint_report.txt  coverage_summary.txt  dependency.svg  snyk_report.json  snyk_code_report.txt
              privileges.txt  privileges.png  snyk-analysis.png  snyk-code-analysis.png  actions_success.png
              module_5_report.pdf
../.github/workflows/    ci.yml (Module 5), tests.yml (Module 4, untouched)
```

`src/` modules import each other flatly (`from models import ...`) and resolve through the editable install
([CHG-01](#chg-01)); `src/` is deliberately not a package, to keep parity with Module 3.

# Reference: what changed and why

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

<a id="chg-11"></a>

### CHG-11: Pull Data no longer creates the table

**Problem.** `pull_data.load_records()` called `create_table()` on every pull,
so it could work on a fresh database. `CREATE TABLE IF NOT EXISTS` is checked
against the account's `CREATE` privilege on the schema before it looks at
whether the table exists, and `COMMENT ON` needs ownership. A least-privilege
runtime account could do neither, so Pull Data would have failed.

**Decision.** The pull issues no DDL. Creating the schema is the owner's job,
done once with `python3 src/load_data.py`, which now connects as the owner
role. If the table is missing or the grants were never applied, the pull stops
with a plain message that points at `sql/grants.sql`, and the driver's own text
is not shown.

**Trade-off.** A pull against a database nobody has set up now fails instead of
quietly creating it. Schema changes are a deployment step, not something a web
request should be able to do.

**Verified by.** `tests/test_least_privilege.py`: `test_pull_succeeds_as_app_role`
and `test_pull_route_succeeds_end_to_end_as_app_role` show the minimum is also
sufficient; `test_load_records_issues_no_ddl` wraps the connection in a spy and
shows every statement is a `SELECT` or an `INSERT`. `tests/test_pull_pipeline.py`
covers the privilege-error message.

<a id="chg-12"></a>

### CHG-12: two database roles, with the privileges written down

**Problem.** Module 4 ran as a superuser. Any injection, or any bug, would have
had the whole server: it could drop the table, read other databases, or create
roles.

**Decision.** `sql/roles.sql` creates `gradcafe_owner`, which owns the table
and does schema setup and the bulk load, and `gradcafe_app`, which the running
app and Pull Data use. Neither is a superuser, and neither can create databases
or roles, replicate, or bypass row security. Only those two accounts, and
superusers, can connect to the database. `sql/grants.sql` gives `gradcafe_app`
`SELECT` and `INSERT` on `applicants` and nothing else: `SELECT` serves the page,
the search, and the pull's read of the newest entry, and `INSERT` serves Pull
Data (`ON CONFLICT DO NOTHING` needs no `UPDATE`). There is no `UPDATE`,
`DELETE`, `TRUNCATE`, `REFERENCES` or `TRIGGER`, no sequence grant, and no
`ALTER DEFAULT PRIVILEGES`. `sql/migrate_ownership.sql` moves an existing table
under the owner. All three scripts can be run again safely.

**Trade-off.** The worst the runtime account can do is read the public
applicant rows and add more of them. That is the point, and it is also a real
limit: it cannot correct or remove a bad row, so that takes the owner.

**Verified by.** `tests/test_least_privilege.py`, connected as the real
accounts: `test_role_attributes`, `test_table_privileges` for each privilege,
`test_ddl_denied` for ten statements (`DROP`, `ALTER`, `CREATE TABLE`,
`TRUNCATE`, `COMMENT`, `UPDATE`, `DELETE`, `CREATE ROLE`, `CREATE DATABASE`,
`GRANT`), each raising `InsufficientPrivilege`, and a check that PUBLIC holds
no privilege on the table.

<a id="chg-13"></a>

### CHG-13: the test fixtures connect as the owner, the application as the app role

**Problem.** Tests that run as a superuser prove nothing about least privilege:
they would pass even if the app role were useless. But the fixtures have to
create the schema and `TRUNCATE`, which the app role must not be able to do.

**Decision.** Two test URLs. `TEST_DATABASE_URL` names the runtime account and
is what every application test connects as. `TEST_ADMIN_DATABASE_URL` names the
owner, and only the fixtures and the least-privilege tests use it. Neither has
a default. `TEST_DATABASE_URL` was introduced in Phase 2 (A2.3); this phase adds
the admin URL and the split.

**Trade-off.** A db test now needs two URLs and two roles set up, not one
connection string. The setup is documented under
[Database setup](#database-setup), and the CI workflow does it.

**Verified by.** `tests/test_least_privilege.py::test_app_fixture_connects_as_app_role`
asks the database who it is connected as, so a harness that silently ran as a
superuser would fail.

<a id="chg-10"></a>

### CHG-10: a failed pull can no longer leave the app stuck busy

**Problem.** The pull route caught `Exception`, and Pylint flags a catch that
broad. Narrowing it to a list of expected errors, on its own, would have
created a worse bug: any error not on the list would skip the code that clears
the busy flag, leaving `busy` True for the life of the process. Every later
pull would be refused with a 409, so one failure would become a permanent
outage.

**Decision.** `pull_data.PULL_FAILURES` names the failures a pull is expected to
end in: its own `PullError`, a database error from either driver, an
`OSError`, and a Selenium `WebDriverException`. The job clears busy in a
`finally` block, whatever happens. An expected failure gets its own message and
a JSON 500. An unexpected one still clears busy, then reaches a registered 500
handler that answers in the same JSON shape and never repeats the exception's
text to the client. Nothing is swallowed.

**Trade-off.** An unexpected exception now shows up as a 500 and a server-log
traceback instead of being folded into the pull's own error message. That is
the right place for a bug to be loud, but it means the test double that raised a
bare `RuntimeError` had to raise `PullError`, which is what a real scrape
failure is (A6.3).

**Verified by.** `tests/test_buttons.py`: `test_unlisted_exception_clears_busy`
fails a pull with an exception nobody listed and then shows the next pull is
accepted, not refused; `test_unhandled_error_returns_json_500` checks the
response shape and that the exception text does not leak;
`test_every_anticipated_failure_is_a_json_500_and_clears_busy` runs each member
of the tuple. Removing the `finally` fails the first, and putting `except
Exception` back fails the second and Pylint.

<a id="chg-14"></a>

### CHG-14: the scrape helpers `pull_data` uses are public

**Problem.** `pull_data.py` called five helpers of `scrape.py` that began with an
underscore, which says "do not call this from outside". The signal was false:
they were already a cross-module API, and Pylint rightly flagged each call as
protected access.

**Decision.** `start_browser`, `fetch_html`, `build_url`, `page_path` and
`next_cursor` lost their underscores. Helpers used only inside `scrape.py`
keep theirs.

**Trade-off.** They are now a public contract, so renaming them later is a
breaking change. They already were one in practice.

**Verified by.** `tests/test_scrape.py::test_public_api_surface` checks the five
public names exist, the five private ones do not, and that `pull_data.py`
contains no `scrape._` reach-in. The existing scrape and pull tests were renamed
and still pass.

<a id="chg-15"></a>

### CHG-15: `scrape_data` takes a window and options, not nine arguments

**Problem.** `scrape_data` had nine positional parameters and 17 local
variables: easy to call in the wrong order, and Pylint counts both
(`too-many-arguments`, `too-many-positional-arguments`, `too-many-locals`).

**Decision.** `scrape_data(window, options=None)`. `ScrapeWindow` holds the two
dates, and `ScrapeOptions` holds every other knob with its default in one
place. Both are frozen dataclasses. The page loop moved into
`_scrape_pages()`, so each function does one thing. Behavior, including resuming
a previous run and closing the browser even when a page fails, is unchanged.

**Trade-off.** Every caller changes from nine keywords to two objects, and the
tests had to change with them.

**Verified by.** `tests/test_scrape.py`: `test_options_defaults`,
`test_window_and_options_are_immutable`, `test_scrape_data_takes_a_window_and_optional_options_only`,
and the existing scrape tests, all rewritten to the new call. A new test shows
the browser is closed when a page raises.

<a id="chg-16"></a>

### CHG-16: the SQLAlchemy false positives are cleared without a disable

**Problem.** 22 of the original Pylint messages were not defects. Pylint's
type inference cannot see through `sqlalchemy.func`, so every `func.count()`
reported "not callable", and it read `sessionmaker[Session]` as subscripting
something that is not subscriptable. Selenium's `webdriver.Chrome` had the same
problem.

**Decision.** `count` is imported from `sqlalchemy.sql.functions`, where
Pylint can resolve it. The two generic annotations are quoted, and Chrome is
imported from the module that defines it. No code behavior changes.

**Trade-off.** The import is slightly less idiomatic than `func.count()`, and a
future reader may wonder why. The reason is recorded here and in the module.

**Verified by.** `tests/test_orm_queries.py::test_compiled_sql_unchanged`, for
all eleven statements, compares the compiled SQL with the Module 4 snapshot taken
before any change in Phase 0. It requires the Module 4 text word for word,
followed by exactly one `LIMIT` clause, and the Module 4 parameters plus exactly
one new one (amendment A6.1). It was shown to fail when a parameter changes or
a clause is added.

<a id="chg-17"></a>

### CHG-17: Pylint is configured, not appeased

**Problem.** A `.pylintrc` that raises thresholds or disables messages makes a
score of 10.00 mean nothing, and an inline `# pylint: disable` hides the finding
at the line that caused it.

**Decision.** Findings are fixed in the code. `.pylintrc` contains the source
root and one classification: a SQLAlchemy declarative base, and the mapped class
that inherits it, are a table definition with columns and no methods by design,
so they are exempt from the one rule that counts methods. `.editorconfig`
enforces a final newline and the line limit in the editor, so the formatting
messages do not come back. There are zero inline disables.

**Trade-off.** Fixing the code costs more than a disable, and a few fixes
(grouping arguments, extracting a function) are changes you would not otherwise
make. That is the point: the score then says something.

**Verified by.** `tests/test_lint_policy.py`: `test_pylintrc_relaxes_nothing`
requires exactly those two entries, `test_pylintrc_sets_no_threshold_or_exclusion`
rules out the usual escape hatches by name, `test_no_inline_disables` scans
`src/`, and `test_pylint_scores_ten_with_no_messages` runs Pylint and requires
`10.00/10` with no message line. `pylint_report.txt` is the committed output.

<a id="chg-19"></a>

### CHG-19: a four-job CI workflow, `ci.yml`

**Problem.** Module 4's workflow ran one job. A single red job does not say which
requirement broke, and a check that is part of a larger job is the first to be
loosened when that job is slow.

**Decision.** `.github/workflows/ci.yml` has four jobs that fail independently:
`lint` (Pylint must score exactly 10.00), `dependency-graph` (pydeps and Graphviz
must build a valid `dependency.svg`, uploaded as an artifact), `snyk` (every pinned
package must have no finding at or above high, with Snyk Code report-only), and
`test` (the full suite with 100% coverage, on pip and on uv, against a
PostgreSQL 16 service). The test job builds the same two least-privilege roles as
production, from throwaway random passwords that are masked in the log and turned
into SCRAM verifiers before they reach the server. Module 4's `tests.yml` is
untouched and keeps testing `module_4`.

**Trade-off.** Four jobs install the environment four times, so a push costs more
runner minutes than one job would. The Snyk job is skipped with a notice, not
failed, when no token is available (a pull request from a fork), so that case is
not a red mark that means nothing.

**Verified by.** `tests/test_ci_config.py` parses the workflow with PyYAML and
asserts each requirement by name (`test_four_jobs`, `test_pylint_fail_under_10`,
`test_svg_validation_step`, and more), and was shown to fail when the lint
threshold is lowered or the Snyk step is made non-failing. It cannot replace a
green run, which is the real evidence: see `actions_success.png`.

<a id="chg-21"></a>

### CHG-21: the role table holds variable names as a pair, not a `"password"` key

**Problem.** Snyk Code flagged `{"user": "DB_USER", "password": "DB_PASSWORD"}` as a
hardcoded password. It was a false positive: the string is the *name* of an
environment variable. But the shape invited the misreading, for a scanner and
for a person skimming the code.

**Decision.** `ROLE_ENV` maps each role to a `(user variable, password variable)`
pair. Nothing in `src/` now has a `"password"` key holding a string literal, and a
test checks that.

**Trade-off.** None in behavior. The table is slightly less self-describing than a
dict, and the comment above it says what the two positions are.

**Verified by.** `tests/test_config.py::test_role_env_maps_each_role_to_a_user_and_password_variable`,
`::test_no_password_key_holds_a_string_literal_in_src` (an AST check of the pattern
Snyk's rule looks for, shown to fail when one is added), and the existing
`::test_env_example_lists_every_variable_the_code_reads`.

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

### Phase 5 amendments

- **A5.1 The real database was migrated too.** The plan's scripts assume a
  database named `gradcafe`; yours is `gradcafedb`, so the scripts take the name
  as a variable. `migrate_ownership.sql` moved the existing table to
  `gradcafe_owner` and applied the grants, and `.env` now connects the app as
  `gradcafe_app`. The data was not touched, and the change reverses with
  `ALTER TABLE applicants OWNER TO <previous owner>`.
- **A5.2 The scripts are re-runnable.** `roles.sql` creates a role only if it is
  missing and otherwise updates it, which is also how a password is rotated, and
  `grants.sql` first strips every privilege so a hand-added grant does not
  survive.
- **A5.3 No cleartext password is sent, typed, or logged.** The plan passed
  passwords to `psql -v`. Checking the server first showed two leaks that would
  have created: the argument is visible in the process list, and
  `log_min_error_statement` writes a failed statement, password included, to a
  log file every local user can read. So `roles.sql` takes SCRAM-SHA-256
  verifiers from the environment, made by the new `scripts/scram_verifier.py`.
  The passwords were generated in memory and written only to the gitignored
  `.env`. See [Credentials were checked for leaks](#credentials-were-checked-for-leaks).
- **A5.4 `PUBLIC` is revoked,** on the database and on the table, so the grants
  hold for every account on the server and not only the two named.
- **A5.5 The Pull Data check uses an existing row.** To prove the account in
  `.env` can use the pull path without adding data to your real database, the
  gate re-sends a row that is already present: `ON CONFLICT DO NOTHING` still
  needs the `INSERT` privilege, and nothing is written.
- **A5.7 A missing table is "does not exist", not "permission denied".** The
  least-privilege tests caught it: with the table dropped, a pull raised a raw
  `UndefinedTable` instead of the clear message CHG-11 promised, because the
  account cannot tell the two cases apart. `load_records` now maps both errors to
  one message, and `test_load_records_maps_a_privilege_error_to_a_clear_message`
  covers each.
- **A5.8 The leak check is permanent.** `scripts/check_credential_leaks.py`
  runs in the gate from Phase 5 on, so a password committed, logged, or left in
  history later fails the gate and does not wait for a manual look.
- **A5.9 No account can create temporary tables.** `REVOKE ALL ON DATABASE ...
  FROM PUBLIC` also removes the `TEMP` privilege PostgreSQL grants to everyone
  by default, from the owner as well as the app role. Nothing in the project
  uses temporary tables, and `test_ddl_denied` checks the app role is refused.
- **A5.10 One wrong expectation about `GRANT`.** A `GRANT` the app role is not
  entitled to make is answered with a warning, not an error, and does nothing.
  The test now checks it changed nothing, instead of expecting an exception.
- **A5.6 `privileges.png` is committed and was checked against the database.**
  It is a screenshot of `\dp applicants` on `gradcafedb`. It was compared with the
  live output and matches: `gradcafe_owner=arwdDxtm` and `gradcafe_app=ar`, which
  is `INSERT` and `SELECT` only. It shows table privileges but not role
  attributes, so `privileges.txt` also carries `\du` and the per-privilege table.
- **A5.11 Snyk Code was confirmed enabled, without sending the project.** It was
  run on one throwaway file outside the repository. It authenticated as the org,
  performed a static code analysis, and reported no issues, so Phase 8 can rely on
  it. The leak-check instruction in the section above came from Josh at the
  Phase 5 go-ahead.

### Phase 6 amendments

- **A6.1 Compiled-SQL check allows exactly the Phase 3 LIMIT.** Phase 3
  adds a LIMIT to every ORM statement, so the compiled SQL can no longer equal
  the Phase 0 snapshot. Phase 6's `test_compiled_sql_unchanged` therefore
  checks every `*_stmt()` builder against the Phase 0 snapshot with one
  allowance. The compiled text must be the snapshot text plus exactly one
  trailing `LIMIT` clause. The bound parameters must be the snapshot's plus
  that one limit value. The snapshot is never re-captured, so the test still
  shows that the LIMIT is the only change.
- **A6.2 Selenium had the same false positive.** `webdriver.Chrome` reported
  "not callable" for the same reason `func.count()` did. It is now imported from
  `selenium.webdriver.chrome.webdriver`, and the tests replace `scrape.Chrome`.
- **A6.3 The failing test double raises `PullError`.** `failing_scraper` raised a
  bare `RuntimeError`, which CHG-10 correctly no longer treats as an anticipated
  failure. It now raises what a real scrape failure raises, and separate tests
  cover an exception nobody listed.
- **A6.4 `create_app` uses `services.x` directly.** Unpacking `Services` into five
  local names pushed it to 16 locals. Using the attributes is clearer and keeps it
  under the limit with no change in behavior.
- **A6.5 Two smaller fixes.** The explicit `return None` in `run_in_background`
  is gone (the function returns `None` anyway, as its docstring says), and the
  `__main__` handler in `pull_data.py` catches `PULL_FAILURES`, so anything
  unexpected shows Python's own traceback.
- **A6.6 The suite checks the score itself.** `test_pylint_scores_ten_with_no_messages`
  runs Pylint inside pytest, about five seconds, so the rubric number is
  verified by every test run and not only by the gate and CI.
- **A6.7 Where the 52 baseline messages went.** 20 `not-callable` and 2
  `unsubscriptable-object` false positives (CHG-16), plus Selenium's one (A6.2);
  9 long lines and 6 missing final newlines (formatting, fixed in the code); 5
  protected accesses (CHG-14); 2 broad catches (CHG-10); 4 argument-count and
  1 local-count message (CHG-15); 2 `too-few-public-methods` (CHG-17); 1 useless
  return (A6.5). Phase 3 had already removed the f-string line-length hits.

### Phase 10 amendments

- **A10.4 The README was restructured for the reader.** It had grown with the build: a status section that had gone
  stale, a Module 4 checklist, and a Module 4 testing section. It now opens with a table of what to verify and the
  command that verifies it, then how to get the environment running, then the security tooling, CI, tests and
  architecture, and only then the reference material (the Change Register detail, the amendments, the development
  process, and the carried-over application reference as an appendix). Amendment A2.8 below describes an
  earlier first pass and is kept as history.

- **A10.1 Cruft removed.** Seven tracked files that nothing reads were deleted
  (all remain in git history and in `module_4/`): `github.txt` (a Module 4 note with the
  repository URL), `check_llm.py` and `run_llm.sh` (Module 2 helper scripts for the
  standardizer, referenced by nothing), `llm_hosting/all` (a captured shell error
  message, committed by accident), `sql/gre_check.sql` and `sql/questions_scratch.sql`
  (Module 3 investigation scratch, executed by nothing), and `data/applicant_data.json`
  (15 MB, the Module 2 pre-LLM intermediate: no code or test reads it, and
  `llm_extend_applicant_data.json` is a superset). Kept on purpose, because
  something depends on them: `llm_hosting/` (Pull Data's standardizer), `docs/`,
  `data/llm_extend_applicant_data.json` (the loader's default and the parity test), and the
  snapshots. The suite was re-run after the deletions: 604 passed, 100%.
- **A10.2 `coverage_summary.txt` is Module 5's.** It was Module 4's file (102 tests);
  it is now the output of `pytest > coverage_summary.txt`.
- **A10.3 The report is built by a script.** `report/build_report.py` assembles
  `module_5_report.pdf` from the committed evidence, so it can be regenerated and
  its figures are read from the repository and not retyped.

### Phase 9 amendments

- **A9.6 The first CI run found three tests that depended on a developer's `.env`.**
  Three of four job types were green on the first push (`lint`, `dependency-graph`,
  `snyk`), and both `test` legs failed with 601 passed and 3 failed, which is what a clean
  machine is for. Two tests needed `DB_HOST`, which only a local `.env` supplied. A
  third compared the full third-party graph, which differs between a Mac and Linux.
  The suite is now hermetic: `conftest.py` switches the `.env` loader off and takes
  only the two test-database URLs from it, by name, so a local run sees what CI sees;
  the two tests set their own configuration; and the graph test compares every import
  the project itself makes. The least-privilege tests, which depend on the CI role
  bootstrap, passed on the first run.

- **A9.7 CI runs on every push and pull request.** The plan filtered the workflow to
  changes under `module_5/`. The assignment says it "runs on every push/PR", so the
  filter was removed, and `test_the_workflow_runs_on_every_push_and_pull_request` fails if
  a branch or path filter is added back.
- **A9.1 The gate has two stages, because a green run cannot exist before the push.**
  `scripts/gate.sh 9` first checks everything that can be checked offline: the
  workflow's tests and the standard gate. The workflow is then committed and pushed.
  Once the run is green and the screenshot is replaced, `GATE_CI_LIVE=1 scripts/gate.sh 9`
  requires a successful run of the pushed commit and a screenshot that is no longer
  Module 4's, and that run is the one recorded in the Gate Log.
- **A9.2 The Snyk job calls `scripts/snyk_scan.sh`,** not a bare `snyk test`, for the
  reason in A8.1. It is skipped with a notice when no token is available.
- **A9.3 The test job needs Graphviz.** One of the tests regenerates `dependency.svg`
  and compares it with the committed graph, so the runner installs `dot`.
- **A9.4 No cleartext password reaches `psql` in CI either.** The roles are made from
  per-run random passwords, masked in the log, converted to SCRAM verifiers, and passed
  in the environment, the same as the README's Database setup. The only literal is
  the throwaway superuser password of the ephemeral Postgres service.
- **A9.5 `actions_success.png` is Josh's** and must show the Module 5 run, not Module 4's.

### Phase 8 amendments

- **A8.1 Snyk cannot read the universal lock directly.** `requirements.txt` carries
  environment markers (`colorama==0.4.6 ; sys_platform == 'win32'`) so one file
  serves macOS, Linux, and Windows. Snyk inspects the installed environment and
  does not evaluate markers, so `snyk test --file=requirements.txt` stops with
  "Missing required packages" for `cffi`, `greenlet` and `pycparser`, which are
  correctly not installed on this machine. `--skip-unresolved` does not cover it.
  The lock is right and the scanner has a limit.
- **A8.2 The scan evaluates the markers itself and loses no package.**
  `scripts/snyk_requirements.py` applies each marker with the `packaging` library
  pip uses and writes two marker-free files: the 65 pins that apply here, and the 5
  a marker excludes (`cffi`, `colorama`, `greenlet`, `pycparser`, `tzdata`).
  `scripts/snyk_scan.sh` scans the first in the project environment and the second
  in a scratch environment that installs just those pins. All 70 are scanned, and a
  test fails if the two groups ever stop covering the lock.
- **A8.3 Two packages were upgraded, and the suite re-run.** `urllib3` 2.7.0 to
  2.8.0 (two high, one medium) and `python-dotenv` 1.0.1 to 1.2.4 (one medium). Both
  were already allowed by the compatible-release ranges, so `setup.py` raised the
  floors to force the fix and the lock was regenerated: exactly two lines changed.
  All 563 tests passed on the new versions, and the gate was re-run.
- **A8.4 Snyk Code's two findings were triaged, not silenced.** The password
  warning was a false positive that is now removed from the code (CHG-21). The
  Low path-traversal note is an accepted risk: the path is a command-line argument
  chosen by the person running the tool. The reasoning is in
  `report/snyk_triage.md`.
- **A8.5 The CI Snyk step needs the same two-group scan.** Phase 9 calls
  `scripts/snyk_scan.sh` rather than a bare `snyk test`, for the reason in A8.1.
- **A8.6 The `llm_hosting/` scan was not done.** The plan marked it informational
  and eligible to cut under the time limit. `llm_hosting/requirements.txt` is a
  separate, instructor-provided environment that is not part of the submitted
  application.
- **A8.7 Screenshots are Josh's, and were checked.** `snyk-analysis.png` and
  `snyk-code-analysis.png` are screenshots of the two commands, which only a
  terminal on his machine can produce. Each was compared with the committed
  evidence: both dependency groups report no vulnerable paths (65 and 5
  packages), and Snyk Code shows one open LOW finding at `load_data.py` line 398.
- **A8.8 Two explanatory sections were added at Josh's request.** "Upgrading
  dependencies when a vulnerability is known" records what was found and why a
  fixed version is taken and not argued around. "False positives: refactor the
  code, even when you know it is safe" records why code is reshaped to avoid a known
  false positive (recurring investigation, alert fatigue, hidden suppressions,
  ambiguity for people) and where that stops, with the path-traversal note as the
  counterexample.

### Phase 7 amendments

- **A7.1 The graph is collapsed to one node per package.** The plan's default,
  `--max-bacon=2`, draws every submodule of psycopg, SQLAlchemy and Flask. That
  was 156 KB and buried the project's own structure. `--max-module-depth=1`
  keeps all ten project modules and draws each third-party package as one node:
  29 KB, ten modules and thirteen packages. The command is recorded in the
  README, the summary, and the test that regenerates the graph.
- **A7.2 Arrows point from the imported module to its importer.** That is
  pydeps's convention and the reverse of what many readers expect, so the report
  says so beside the picture.
- **A7.3 The plan's chain `pull_data -> scrape -> clean -> load_data` was
  conceptual.** In the imports, `pull_data` imports all four of `scrape`, `clean`,
  `load_data` and `models`, and `clean` imports `scrape`. The explanation
  describes what the graph shows.
- **A7.4 The graph is tested, not just committed.** The tests regenerate it and
  compare nodes and edges, so an import added later fails the build until the graph is
  refreshed. They also recompute the report's claims (the hub, the shared leaf,
  no cycles) from the edges, so the prose cannot drift from the picture. They need
  Graphviz installed, which the Fresh Install section already requires.
- **A7.5 BeautifulSoup is beyond the edge.** The graph stops two imports from
  `app.py`, and `clean` is two away, so its parser is the first package left off.

## Development process

### Module 5: hard input and output gates, governed by tests

Module 4 was built spec-driven, with a plan that was rewritten as work went on.
Module 5 added the part that makes a plan checkable: **every phase has a hard
entry gate and a hard exit gate, and the exit gate is a set of tests that must
exist, be collected, and pass before the phase counts as done.** The process is
deterministic and repeatable because three artifacts are kept in step: `PLAN.md`
says what each phase must achieve, `CHANGES.md` (the Change Register) records every
design change with its reason and the tests that verify it, and
`scripts/gate.sh` enforces both.

**The gates.** `scripts/gate.sh entry N` refuses to start phase N unless the
previous phase is committed and logged, the working tree is clean, and the
environment is the pinned one. `scripts/gate.sh N` runs the exit gate: the full
suite at 100% coverage, a marker on every test, Pylint no worse than the last gate
(exactly 10.00 from Phase 6), no inline disables, no secrets, a Change Register
whose every due row is `done` with a rationale, a README section, and tests that
pytest actually collects, and then the checks specific to that phase. A pass is
recorded against the exact git tree it passed on, and `gate.sh log N` will not write
the Gate Log row unless the commit is that tree. Josh approved every commit and every
push, and the gate output, not the author, says whether a phase is finished.

**Tests before the work they judge.** The exit criteria and the names of the
verifying tests were fixed in `PLAN.md` and `CHANGES.md` before a phase began, and
the gate would not pass until tests with those names existed. Beyond the contract,
four things were done in this order on purpose:

- **Measure against a fixed point.** Before any code changed, Phase 0 captured what
  Module 4 actually answered (all 30,000 rows through every analysis) and the SQL
  its ORM compiled. The Phase 3 and Phase 6 refactors were then judged against that
  snapshot, so "no answer changed" was a test and not an assurance.
- **Make the gate prove it can fail.** The Phase 0 gate adds an unmarked test and
  requires the run to stop. The Phase 3 gate reintroduces an f-string SQL statement
  and requires the guard to reject it. A gate that has never been seen to fail
  proves nothing.
- **Break the code on purpose.** Where a test was written after the code it covers,
  it was then run against a deliberately broken copy (a loosened regex, a removed
  `finally`, a lowered threshold) and required to go red. A test that cannot fail is
  not a gate. Each phase's README section names the break that was tried.
- **Let the tests argue with the plan.** Red results were information. The first
  least-privilege run failed four tests: one was a real bug (a missing table raised a
  raw error instead of a message, A5.7), and the others were wrong expectations. The
  limit test found that the plan contradicted itself on how many digits a limit may
  have (A3.1). The first CI run failed three tests that passed only because of the
  developer's `.env`, so the suite now refuses to read it (A9.6).

**Why it is repeatable.** Each of the 21 Change Register rows states a problem, a
decision, a trade-off and the tests that verify it, and the Gate Log records the
commit, the test count, the coverage and the Pylint score at every exit (102 tests
and 8.30 at the start; 605 and 10.00 now). Where execution diverged from the plan,
an amendment was written down under the phase, 77 of them, so the plan plus its
amendments describes what actually happened and not what was intended. Someone
with the plan, the register and the gate script could replay the module in order,
and would be stopped at the same places for the same reasons. The environment is
pinned (`requirements.txt`, proven by `scripts/fresh_install_check.sh` with pip and
uv), and the checks that guard the process, the secrets scan, the credential-leak
check and the CI workflow, each have their own tests.

**What the gates caught that review would likely have missed.** Two bugs in the gate
script itself, found while logging Phase 1 (A1.6). Two credential-leak routes the
plan would have created (A5.3). Snyk's inability to read a universal lock (A8.1). A
dependency graph that differed between a Mac and a Linux runner (A9.6). In every
case the discovery came from a check failing, not from reading the code.

This module again used Claude Code for the whole of the work, in one continuous
session with the repository, the test runner, a live PostgreSQL and GitHub Actions
within reach. Every number in this README (tests, coverage, Pylint, Snyk) was
produced by running the thing in that session.

### Module 4

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

# Appendix: reference for the carried-over application

The sections below describe the application as it came from Modules 2 to 4 and are kept as reference. They are
accurate for Module 5 except where a section says it is Module 4 history.

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
