# EN 605.256 Modern Software Concepts in Python: Module 3

**Name:** Joshua Latz
**JHED ID:** jlatz1
**Module:** Module 3, Assignment: Database Queries, SQLAlchemy, and Dynamic Webpages
**Due:** Sunday, 20 September 2026, 11:59 PM
**Submitted:** Monday, 21 September 2026 (one day late: my wife needed urgent care on two consecutive days)
**Repository:** https://github.com/5th-legionnaire/jhu_software_concepts (private). This assignment lives under `module_3/`.
**Python:** 3.14.6 (CPython, macOS)
**PostgreSQL:** 18.6 (Homebrew)

## 1. Overview

This module loads the applicant data scraped, cleaned, and LLM-standardized in Module 2 into
PostgreSQL, analyzes it with raw SQL and again with the SQLAlchemy ORM, and presents the results
on a Flask webpage that can pull newly posted Grad Café entries into the database on demand.

| Part | Deliverable | File(s) |
|---|---|---|
| 1 | Load Module 2 data into PostgreSQL | `load_data.py` |
| 2, 3 | Nine required SQL questions and two original questions | `query_data.py` |
| 4 | SQL analysis write-up | `query_results.pdf` |
| 5 | `Applicant` model, Engine, Session | `models.py` |
| 6 | Questions 1, 4, 5, 8, 9 and one original question via the ORM | `orm_queries.py` |
| 7 | SQL versus ORM comparison | this README, section 9 |
| 8, 9, 10 | Analysis page, Pull Data, Update Analysis | `app.py`, `templates/`, `static/`, `pull_data.py` |
| 11 | Data limitations reflection | `limitations.pdf` |

The input is `llm_extend_applicant_data.json`, the Module 2 Part 2 output: 30,000 applicant
records added to Grad Café between 1 January and 14 September 2026.

## 2. Repository Structure

```
jhu_software_concepts/
└── module_3/
    ├── README.md                        # this file
    ├── requirements.txt
    ├── github.txt                       # SSH URL of the repository
    ├── .env.example                     # connection settings template (no secrets)
    ├── .gitignore
    │
    ├── load_data.py                     # Part 1: create_table(), load_data()
    ├── query_data.py                    # Parts 2 and 3: raw SQL analysis
    ├── models.py                        # Part 5: Applicant model, Engine, Session
    ├── orm_queries.py                   # Part 6: SQLAlchemy analysis
    ├── app.py                           # Parts 8 to 10: Flask application
    ├── pull_data.py                     # Part 9: scrape, clean, standardize, load pipeline
    ├── scrape.py                        # from Module 2, used by Pull Data
    ├── clean.py                         # from Module 2, used by Pull Data
    ├── run_llm.sh                       # from Module 2
    ├── llm_hosting/                     # instructor-provided LLM standardizer, unmodified
    ├── llm_extend_applicant_data.json   # input: Module 2 Part 2 output, copied unmodified
    ├── pull_work/                       # Pull Data pages and log (gitignored)
    │
    ├── templates/index.html             # the analysis page
    ├── static/style.css                 # page styles
    │
    ├── sql/
    │   ├── gre_check.sql                # value-range audit behind the validity ranges (section 7.2)
    │   └── questions_scratch.sql        # Q8/Q9 record-level agreement check (section 7.4)
    ├── docs/
    │   ├── query_results.docx           # editable draft of query_results.pdf
    │   └── limitations.docx             # editable draft of limitations.pdf
    ├── query_results.pdf                # Part 4
    ├── limitations.pdf                  # Part 11
    └── screenshots/
        ├── sql_output.png               # raw SQL console output
        ├── orm_output.png               # SQLAlchemy console output
        ├── flask_page_pt8.1.png         # the running webpage (Part 8), top
        ├── flask_page_pt8.2.png         # middle
        └── flask_page_pt8.3.png         # bottom
```

All Python files sit at the top level because they import one another by module name, and
`templates/` and `static/` sit beside `app.py` because that is where Flask looks for them. The
Module 2 working folders (`raw_pages/`, `chunks/`) and `applicant_data.json` are not copied into
this module; they remain in `module_2/`.

Excluded via `.gitignore` and from the Canvas zip: `.env` (holds the database password), both
virtual environments, `__pycache__/`, the TinyLlama model weights (`*.gguf`, about 650 MB,
downloaded automatically on first run), and `pull_work/`.

## 3. Installation and Setup

### 3.1 PostgreSQL
A running PostgreSQL server and a database are required. The loader creates the table but not the
database.

```bash
createuser --superuser postgres   # only if the role does not exist (e.g. Homebrew installs)
psql -d postgres -c "ALTER USER postgres PASSWORD 'choose-one';"
createdb gradcafedb
```

Homebrew's `initdb` creates a superuser named after the macOS account rather than a `postgres`
role, so on those installs the role must be created by hand. Put the chosen password in `.env`
(section 3.2).

### 3.2 Connection settings
All code reads the standard libpq environment variables (`PGHOST`, `PGPORT`, `PGDATABASE`,
`PGUSER`, `PGPASSWORD`). `python-dotenv` populates them from a `.env` file in `module_3/` if one
exists; variables already set in the shell take precedence.

```bash
cp .env.example .env
# edit .env and set PGPASSWORD (and anything else that differs)
```

No credentials, hosts, or machine-specific paths are hard-coded anywhere, and `.env` is never
committed.

### 3.3 Python environment
One environment covers the loader, both query programs, the Flask application, and the Module 2
scraper that Pull Data invokes.

```bash
cd module_3
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

| Package | Version | Used by |
|---|---|---|
| `psycopg[binary]` | 3.3.6 | `load_data.py`, `query_data.py`, and SQLAlchemy's PostgreSQL driver |
| `SQLAlchemy` | 2.0.54 | `models.py`, `orm_queries.py`, `app.py` |
| `python-dotenv` | 1.0.1 | connection settings |
| `Flask` | 3.1.3 | `app.py` |
| `beautifulsoup4`, `soupsieve` | 4.15.0, 2.9.2 | `clean.py` |
| `selenium` | 4.49.0 | `scrape.py` |
| `urllib3` | 2.7.0 | `scrape.py` (pinned as in Module 2) |

The database driver is psycopg 3, whose PyPI package is named `psycopg` (`psycopg2` is the previous
major version). The `[binary]` extra bundles libpq, so no PostgreSQL client headers or compiler are
needed; prebuilt wheels exist for CPython 3.14 on Apple silicon.

### 3.4 LLM standardizer environment
The standardizer keeps its own environment, as in Module 2, because it depends on
`llama-cpp-python`, which compiles native code. Pull Data runs it in this environment.

```bash
cd module_3/llm_hosting
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3.5 Browser setup for Pull Data
Grad Café sits behind Cloudflare. As in Module 2, the verification must be cleared once, by hand,
in the persistent Chrome profile the scraper uses (`~/.gradcafe-chrome-profile`). See the Module 2
README, sections 4.1 and 6.2.

## 4. How to Run

All commands run from `module_3/` with the main environment active.

```bash
python3 load_data.py      # Part 1: create the table and load the Module 2 data
python3 query_data.py     # Parts 2 and 3: raw SQL results to the console
python3 orm_queries.py    # Part 6: SQLAlchemy results to the console
python3 app.py            # Parts 8 to 10: then open http://127.0.0.1:8080
```

`load_data.py` prints a summary on completion. Running it a second time is safe and changes
nothing:

```
Read 30000 records: 30000 inserted, 0 already present, 0 skipped (no result id in url)
Read 30000 records: 0 inserted, 30000 already present, 0 skipped (no result id in url)
```

To inspect the table: `psql -d gradcafedb -c '\d+ applicants'` shows columns, types, and
descriptions.

## 5. Part 1: Data Schema

### 5.1 Required columns
The table implements the assignment schema exactly. Each column's description is stored in the
database catalog via `COMMENT ON COLUMN`, verbatim from the assignment, so it is visible to anyone
inspecting the table rather than living only in the source code.

| Column | Type | Description |
|---|---|---|
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

`p_id` is the primary key. `url` additionally carries a `UNIQUE` constraint.

### 5.2 Additional columns
Three further columns are appended after the required ones. They are not part of the assignment
schema, and their descriptions are my own rather than the assignment's.

| Column | Type | Description |
|---|---|---|
| `program_name` | text | Program name alone, as presented by the site |
| `university` | text | University name alone, as presented by the site |
| `decision_date` | text | Date the decision was given, as presented by the site (no year) |

They are included so that no field parsed in Module 2 is dropped on the way into the database.
The Module 2 requirement to preserve applicant-provided data carries forward: a loader that
silently discards three of the seventeen parsed fields would undo that.

`university` matters most. The Module 2 README (section 8) measured the LLM standardizer's
`llm-generated-university` against the site's own university text and found roughly 550 records,
about 1.8%, where the model substituted a different institution: `University of Michigan` became
`University of Milan` in 287 records, for example. That is directly relevant to Question 9, which
compares the original fields against the LLM fields (see section 7).

Appending the extra columns after the required ones, rather than interleaving them, keeps the
required schema recognizable in order and makes the additions obvious. They are mapped in the
`Applicant` model as well, so the model reflects the table as it actually exists.

## 6. Part 1: Loading Approach

### 6.1 Field mapping and conversion
Each Module 2 record is converted by `_prepare_record()`:

| JSON key | Column | Conversion |
|---|---|---|
| `url` | `p_id` | Result id parsed from the permalink, e.g. `.../result/1020482` → `1020482` |
| `date_added` | `date_added` | `"Sep 12, 2026"` → `2026-09-12` |
| `US/International` | `us_or_international` | Renamed only |
| `GPA` | `gpa` | Label stripped: `"GPA 3.40"` → `3.4` |
| `GRE` | `gre` | Label stripped: `"GRE 163"` → `163.0` |
| `GRE V` | `gre_v` | Label stripped: `"GRE V 158"` → `158.0` |
| `GRE AW` | `gre_aw` | Label stripped: `"GRE AW 4"` → `4.0` |
| `Degree` | `degree` | Renamed only |
| `llm-generated-program` | `llm_generated_program` | Renamed only |
| `llm-generated-university` | `llm_generated_university` | Renamed only |
| all others | same name | None |

Module 2 deliberately kept the site's label prefixes on GPA and GRE values and deferred numeric
conversion to this module. That conversion happens here, and only here.

### 6.2 Missing values
Module 2 represents a missing value as an empty string. Every such value is loaded as SQL `NULL`,
in every column, so "missing" has one representation in the database. This is also a hard
requirement for the typed columns: PostgreSQL rejects `''` as a `float` or `date`. A score or date
that is present but cannot be parsed is likewise loaded as `NULL` rather than failing the run.
Non-empty text is passed through unmodified: not trimmed, re-cased, or otherwise altered.

`NULL` is also what makes the assignment's averaging rule hold without special handling: SQL
`AVG()` ignores `NULL`, so an applicant contributes to exactly the averages whose metric they
reported.

### 6.3 Why `decision_date` is text
The site gives decision dates without a year (`"Sep 11"`). Converting to a `date` would mean
inferring the year from `date_added`, which is usually right and occasionally wrong: a December
decision posted in January belongs to the previous year, and nothing in the record says so.
Guessing would put values in the database the source does not support.

### 6.4 Rerunning without duplicates
`p_id` is the Grad Café result id rather than a generated sequence. It is stable across runs and
across sources, so every insert uses `ON CONFLICT (p_id) DO NOTHING`. A rerun skips records already
loaded, and Pull Data can hand the same loader records that overlap the existing data without
creating duplicates or overwriting anything. A generated key would mint a new id for the same
applicant on every run and defeat the primary key as a duplicate guard.

### 6.5 Transactions and error handling
All inserts run in one transaction via psycopg 3's `executemany()`, which pipelines the statements:
either the whole file loads or none of it does. This was verified by forcing an out-of-range id
into the last record of a 3,001-record test file; the load failed and the table stayed empty.
The connection runs in autocommit mode with every write wrapped in an explicit
`connection.transaction()` block, which gives real transaction boundaries in psycopg 3. Table creation and column comments are idempotent.
Database errors are reported and re-raised rather than swallowed, so a failed `CREATE TABLE` stops
the run instead of surfacing later as a confusing insert error. Connection settings are read when
the loader runs, not at import, so importing `load_data` has no side effects.

## 7. Parts 2 and 3: SQL Analysis

Results, full queries, and explanations are in `query_results.pdf`. This section records the
interpretation decisions behind them.

Results from `python3 query_data.py` against the full 30,000-record table:

| Question | Result |
|---|---|
| Q1 Fall 2026 applicant count | 29,576 |
| Q2 Percent international | 46.53% (13,650 of 29,336 classified entries) |
| Q3 Average GPA | 3.77 (n=17,974) |
| Q3 Average GRE Quantitative | 165.83 (n=954) |
| Q3 Average GRE Verbal | 160.70 (n=2,002) |
| Q3 Average GRE Analytical Writing | 4.35 (n=1,807) |
| Q4 Average GPA, American, Fall 2026 | 3.79 (n=10,180) |
| Q5 Fall 2025 acceptance percentage | 47.92% (92 of 192) |
| Q6 Average GPA, accepted, Fall 2026 | 3.76 (n=7,204) |
| Q7 JHU Masters in Computer Science | 8 |
| Q8 Original-field count | 28 |
| Q9 LLM-field count | 28 (difference 0) |
| UQ1 Fall 2026 acceptance rate, usable GPA reported | 40.71% (7,204 of 17,695) |
| UQ1 Fall 2026 acceptance rate, no usable GPA | 31.73% (3,770 of 11,881) |
| UQ2 PhD, American | 25.39% (2,546 of 10,029) |
| UQ2 PhD, International | 26.11% (2,781 of 10,650) |
| UQ2 Masters, American | 68.64% (3,021 of 4,401) |
| UQ2 Masters, International | 67.45% (1,846 of 2,737) |

For reference, ETS reports means of 157.62 Quantitative, 151.39 Verbal, and 3.46 Analytical
Writing across all test takers from July 2022 to June 2025 (GRE General Test Interpretive Data,
Table 1A). The Grad Café averages run roughly one standard deviation higher on each measure; see
`limitations.pdf`.

### 7.1 Matching rules
- **Term:** case-insensitive equality on `term` (e.g. `'fall 2026'`).
- **Acceptance:** `status` equal to `Accepted`, case-insensitive. The column holds exactly four
  values (`Accepted`, `Rejected`, `Wait listed`, `Interview`), because Module 2 split the decision
  date into its own column.
- **Nationality (Question 2):** denominator is every row with a non-`NULL`
  `us_or_international`; numerator is rows equal to `International`. `American` and `Other` count
  in the denominator only. The data holds no `Other` values and 664 blanks, which are excluded.
- **Averages:** plain `AVG()` per metric, which excludes `NULL`s per metric as required.
- **Questions 7 and 8 (original fields):** `program` holds the combined
  `"Program, University"` text as the site presents it, so university and program are matched
  within it. Johns Hopkins matches `johns hopkins`, `john hopkins` (a common misspelling in the
  source), and `jhu`. Degree is matched case-insensitively against `Masters` and `PhD`, which the
  data confirms are the only master's and doctoral research values present (alongside `MFA`,
  `PsyD`, `EdD`, `JD`, `MBA`, and `Other`).
- **Question 9 (LLM fields):** the same filters with university and program matched against
  `llm_generated_university` and `llm_generated_program`; term, degree, and status stay on the
  original fields as the assignment specifies.

### 7.2 Validity ranges for averages
Before writing any averaging query, every numeric column was audited with `gre_check.sql`, which
buckets each value against the scale it is supposed to be on. The results, over all 30,000 rows:

| Metric | Bucket | Count |
|---|---|---|
| `gpa` | 0 to 4.0 | 17,974 |
| `gpa` | above 4.0, up to 4.33 | 57 |
| `gpa` | above 4.33, up to 10 | 77 |
| `gre` | below 130 | 23 |
| `gre` | 130 to 170 | 954 |
| `gre` | 260 to 340 | 1,406 |
| `gre` | above 340 | 9 |
| `gre_v` | below 130 | 1 |
| `gre_v` | 130 to 170 | 2,002 |
| `gre_v` | above 170 | 3 |
| `gre_aw` | 0 to 6 | 1,807 |
| `gre_aw` | above 6 | 80 |

The `gre` column is mostly not quantitative scores. Grad Café labels the field only `GRE`, and
1,406 applicants entered a combined score on the 260 to 340 scale against 954 who entered a
quantitative score on the 130 to 170 scale. A plain `AVG(gre)` would mix the two and describe no
one. The remaining out-of-range values (for example `4`, likely an Analytical Writing score in the
wrong box, and `999`, a placeholder) are not scores on any GRE scale.

Averages therefore include only values on the metric's own scale:

| Metric | Valid range | Included | Excluded |
|---|---|---|---|
| `gre` (quantitative) | 130 to 170 | 954 | 1,438 |
| `gre_v` | 130 to 170 | 2,002 | 4 |
| `gre_aw` | 0 to 6 | 1,807 | 80 |
| `gpa` | 0 to 4.0 | 17,974 | 134 |

The rationale is the assignment's own averaging rule: an applicant contributes to an average only
if they provide that metric, and a value off the metric's scale does not provide it in any usable
sense. The ranges are applied inside the queries only. The table itself holds every value as
reported, consistent with the Module 2 rule against altering source data, and the exclusion counts
are reported alongside each average.

The GPA ceiling removes values impossible on the dominant 4.0 scale. It does not make the average
single-scale: a 3.9 reported on a 4.33 scale is indistinguishable from a 3.9 on a 4.0 scale and
remains included. At 0.7% of reported GPAs, the ceiling moves the average very little either way.

The ranges are defined once, as constants in `query_data.py`, and imported by `orm_queries.py`,
so the raw SQL and ORM answers apply identical filters.

### 7.3 Data window caveat
The dataset covers entries *added* between 1 January and 14 September 2026. That window captures
most of the Fall 2026 cycle but only the tail of Fall 2025, whose decisions were largely posted in
early 2025. Question 5's Fall 2025 acceptance rate is therefore computed over a small subset
consisting of late posters, which is not a random sample of the Fall 2025 cycle. Term counts
confirm it: 29,576 Fall 2026 entries against 192 for Fall 2025. The Fall 2025 denominator is
reported alongside the percentage.

### 7.4 Original questions
- **User question 1 (UQ1):** Among Fall 2026 entries, do applicants who report a usable GPA post acceptances
  at a different rate from those who do not? This measures whether the choice of which fields to
  fill in is itself correlated with outcome, a form of self-reporting bias the limitations
  reflection draws on.
- **User question 2 (UQ2):** How do Fall 2026 acceptance rates differ between American and International
  applicants, for PhD and Masters programs?

Both use the Question 5 definition of acceptance rate (acceptances over all entries in the group,
including interviews and waitlists), so the rates are comparable across questions. In code they
are `uq1()` and `uq2()`, with SQL constants `UQ1_SQL` and `UQ2_SQL`.

UQ1 found a nine-point gap: applicants who report a GPA post acceptances at 40.71% against 31.73%
for those who do not. UQ2 found acceptance rates driven almost entirely by degree type (about 68%
for Masters against about 26% for PhD) and nearly identical across nationality within each degree.

**Why Questions 8 and 9 agree.** A record-level cross-tabulation of the two match conditions
(`questions_scratch.sql`),
under the shared term, status, and degree filters, found all 28 records matched by both methods
and none matched by only one. Equal totals alone would not have shown that. The agreement follows
from the question: the four named universities have distinctive full names, while the LLM
standardizer's confabulations (Module 2 README, section 8) cluster on short, unqualified names,
such as `University of Michigan` completed as `University of Milan` in 287 records. A question
targeting those institutions would likely have produced differing counts.

## 8. Parts 5 and 6: SQLAlchemy ORM

### 8.1 Model, Engine, and Session (`models.py`)
`Applicant` maps the existing `applicants` table using SQLAlchemy 2.x typed declarative mapping
(`DeclarativeBase`, `Mapped[...]`, `mapped_column()`). It maps all fifteen required columns with
their schema types (`Integer`, `Text`, `Date`, `Float`) plus the three additional columns, so the
model reflects the table as it actually exists. `p_id` is the primary key, with autoincrement
disabled because it is the Grad Café result id rather than a generated sequence.

`models.py` maps the table and never creates, alters, or copies it; `load_data.py` owns the schema.
The Engine is built from the same `PG*` settings as `load_data.py`, through `get_db_config()`, so
both access paths reach one database and one table. It uses the `postgresql+psycopg` driver
(psycopg 3; a bare `postgresql` URL would select psycopg2), and `URL.create()` rather than a
formatted string, so a password containing characters such as `@` or `/` cannot corrupt the URL.

The Engine and the `sessionmaker` are created once, on first use, rather than at import. Importing
`models` (from `orm_queries.py`, the Flask app, or a test) therefore has no side effects and does
not fail when the variables are unset. Sessions are used as context managers:

```python
from models import Applicant, get_session
from sqlalchemy import select

with get_session() as session:
    rows = session.scalars(select(Applicant).limit(5)).all()
```

Running `python3 models.py` verifies the mapping against the live database: it compares the
model's columns with the table's actual columns, fails if either side has a column the other
lacks, and reads a row back through the ORM.

### 8.2 ORM queries (`orm_queries.py`)
`orm_queries.py` repeats Questions 1, 4, 5, 8, and 9 and User Question 2 using SQLAlchemy:
`select()`, `where()`, `func.count()`, `func.avg()`, `and_()`, `or_()`, and `case()`, executed
through a `Session`. No handwritten SQL is submitted: the module contains no `text()` construct
and no database cursor. The remaining questions are expressed in the ORM as well, so the Flask
page can read every result through the `Applicant` model without duplicating logic in its routes.

Validity ranges, matching patterns, and formatters are imported from `query_data.py` (constants
and functions only, none of its SQL), so both paths apply identical filters and formatting.
Case-insensitive pattern matching uses `regexp_match(pattern, flags="i")`, which compiles to
PostgreSQL's `~*`, so the same patterns work unchanged.

**Equivalence.** All eleven questions were run both ways against the same database, and the
results were compared field by field. They matched exactly on the real 30,000-record data, and on a
5,000-record synthetic set built to include offsetting LLM errors (a nonzero Question 9
difference) and the word-boundary cases the patterns guard against.

```bash
python3 orm_queries.py          # Part 6 results
python3 orm_queries.py --sql    # also print the SQL SQLAlchemy generated, with parameters
```

## 9. Part 7: SQL versus ORM Comparison

Question 8, answered both ways.

**Raw SQL** (`query_data.py`):

```sql
SELECT COUNT(*)
FROM applicants
WHERE LOWER(term) = 'fall 2026'
  AND LOWER(status) = 'accepted'
  AND LOWER(degree) = 'phd'
  AND program ~* 'computer science'
  AND program ~* 'georgetown|massachusetts institute of technology|\mmit\M|stanford|carnegie mellon|\mcmu\M';
```

**SQLAlchemy** (`orm_queries.py`):

```python
FALL_2026 = _ci_eq(Applicant.term, "fall 2026")
ACCEPTED = _ci_eq(Applicant.status, "accepted")
PHD = _ci_eq(Applicant.degree, "phd")

def q8_stmt():
    return select(func.count()).select_from(Applicant).where(and_(
        FALL_2026, ACCEPTED, PHD,
        _matches(Applicant.program, CS_PATTERN),
        _matches_any(Applicant.program, Q8_UNIVERSITY_PATTERN)))
```

**Comparison.** The ORM's advantage grows with scale. In a larger analytics project, where
many queries are built, reused, and persisted, filters such as `FALL_2026`, `ACCEPTED`, and `PHD`
become shared building blocks defined once and composed everywhere, so a change to how acceptance
is matched happens in one place, each query can be unit tested like any other function, and a team
can extend the `Applicant` model and its filters instead of tracking a growing collection of SQL
strings. The abstraction also buys portability, since SQLAlchemy generates SQL for whichever
database dialect it is pointed at, although this project's regex word anchors (`\m`, `\M`) are
PostgreSQL-specific and would not travel. Raw SQL's advantages are flexibility and readability: a
query can be written, run, and adjusted on the fly in `psql` with no code to commit or debug, as the
`gre_check.sql` audit and the `questions_scratch.sql` overlap check were, and what you read is
exactly what runs. It also gives direct control over the resulting query, whereas the ORM version of
Question 8 compiles to six `~*` conditions joined by `OR`, and debugging it required printing the
generated SQL, which exposed a hazard with no raw-SQL counterpart: SQLAlchemy's literal-value rendering double-escapes the regex backslashes,
so the displayed SQL was subtly wrong even though the executed query was correct.

## 10. Parts 8 to 10: Flask Application

### 10.0 Analysis page (Part 8)
`python3 app.py` serves a single page at `http://127.0.0.1:8080`. It uses port 8080 rather than
Flask's default 5000 because macOS's AirPlay Receiver occupies 5000; set `PORT` to override.

Every result on the page is read from PostgreSQL on each request, through the SQLAlchemy
`Applicant` model: the route calls `all_results()` and `dataset_summary()` from `orm_queries.py`
rather than containing query logic of its own. `build_sections()` in `app.py` only formats those
results for display, with the same formatters as the console output, so the page, the console,
and `query_results.pdf` present identical figures.

The page shows all nine required questions and both user questions, each with its question in
words and its formatted answer. The one deliberate design element is a sample-size bar under
every answer: its length is the share of the dataset the answer rests on, and it turns amber when
that share is under 5%. The GRE Quantitative average (954 entries), the Fall 2025 acceptance rate
(192), and the Question 7 to 9 counts therefore read visibly as thin evidence, which is the
argument of `limitations.pdf` expressed in the layout.

If the database cannot be reached, the page returns HTTP 503 with a message saying what to check,
rather than a stack trace, and recovers on the next request once PostgreSQL is back. An empty
table shows a prompt to run `load_data.py`.

### 10.1 Pull Data (Part 9)
The **Pull Data** button runs `pull_data.py` as a subprocess and returns immediately, so a pull
that takes minutes never blocks the page. The panel beside the button explains what it does. While
the pull runs, a status line shows its latest progress (for example, which page of Grad Café it is
checking); when it ends, the line shows the result, such as how many entries were added.

`pull_data.py` reuses the Module 2 code, unmodified, rather than reimplementing it:

1. **Scrape only what is new.** Grad Café lists entries newest first and result ids increase over
   time, so the scraper starts at the first page and stops at the first page containing an id at
   or below the highest `p_id` in the database. Module 2's resume logic could not be reused for
   this, because it continues toward *older* entries while new ones appear at the *front* of the
   listing. The fetching itself is `scrape.py`'s, so the robots.txt check, the 2-second delay,
   and stopping at the first failed request all carry over.
2. **Parse** the saved pages with `clean.clean_data()`, keeping only entries newer than the
   database.
3. **Standardize** them with the instructor-provided LLM standardizer in its own environment
   (`llm_hosting/.venv`), with the GPU settings tuned in Module 2.
4. **Load** them with `load_data()` from Part 1: one transaction, `ON CONFLICT (p_id) DO NOTHING`,
   so existing rows are never overwritten and a failed pull adds nothing.

**One pull at a time.** The app keeps the handle of the subprocess it started. While that process
is running, the button is disabled, and a second request is answered with a notice instead of a
second scrape. This guards pulls started from the running app; restarting the app mid-pull
forgets the running pull.

**Messages.** Everything `pull_data.py` prints is written for the user, and the page shows its
last line. Each way a pull can stop has its own message saying what happened and what to do next:
a verification check or timeout on Grad Café (complete the check in the Chrome window and click
again), a missing or failed standardizer, or an unreachable database. The full output of the
latest pull is in `pull_work/pull_data.log`.

**Cloudflare.** The scraper uses the same persistent Chrome profile as Module 2. A verification
check is completed by a person in the Chrome window, never by the code.

**Tested** with stand-ins for Chrome and the language model that honor the exact interfaces of
`scrape.py`, `clean.py`, and the standardizer's command line: a one-page pull, an immediate rerun
that found nothing new, multi-page pulls, a double click during a pull (one process ran; the
second click got a notice), and a pull with the standardizer missing (specific message, nothing
added), followed by a successful retry.

### 10.2 Update Analysis (Part 10)
The **Update Analysis** button sits at the top right of the page. It re-reads every result from
PostgreSQL through the ORM and never starts a scrape. Under the button, "Results as of" shows the
time of the latest read, so each update is visibly fresh.

Every click produces a notice rather than a silent refresh. The notice reports how many entries
the database now holds, compared with what the page last showed: for example, "The database now
holds 30,040 entries, 40 more than before," or "the same as before."

**During a pull**, Update Analysis still refreshes, but it leaves the pull running and says so:
new data is currently being retrieved, so the results may not include it yet, and clicking again
after the pull finishes will include the new entries. Reading during a pull is safe, because the
loader commits all of a pull's entries in a single transaction: a read sees the database either
entirely before the new entries or entirely after them, never halfway. If the database cannot be
reached, the notice says so instead of refreshing.

**Tested** in three cases with the same stand-ins: an update with no pull (notice: same as
before), an update during a pull (warning shown, the pull left running, still exactly one pull
process), and an update after a pull added 40 entries (notice: 40 more than before).

## 11. Known Issues

1. **`gre` holds mixed scales.** The assignment describes `gre` as the GRE Quantitative score, but
   the site's `GRE` field holds combined scores for most applicants who report one. Averages use
   only on-scale values; see section 7.2.
2. **LLM standardizer defects carry through.** The acronym-casing and confabulation defects
   documented in the Module 2 README (sections 8 and 9) are present in `llm_generated_university`
   and loaded as generated. They bear directly on Question 9.
3. **Decision dates have no year.** See section 6.3.
4. **Fall 2025 coverage is partial.** See section 7.3.

## 12. Requirements Traceability

Organized by the grading rubric.

### GitHub Repository Setup and Submission (5)
- [x] `github.txt` contains the private repository SSH URL
- [x] Clearly organized `module_3` folder with required files
- [x] Canvas zip and final GitHub version correspond

### PostgreSQL Database Setup and Data Loading (18)
- [x] `load_data.py` connects to PostgreSQL using psycopg
- [x] `applicants` table with the required schema, types, and primary key
- [x] Cleaned Module 2 data inserted
- [x] Missing values, formatting, and repeated loading handled without corruption or duplication
- [x] Readable code, reasonable error handling, no committed credentials

### Raw SQL Query Analysis (22)
- [x] Questions 1 to 9 answered in SQL in `query_data.py`
- [x] Term, status, nationality, university, program, and degree filtering
- [x] Percentages, denominators, NULL handling, averages, and decimal formatting
- [x] Two original questions
- [x] `query_results.pdf` with results, queries, and explanations

### SQLAlchemy ORM (15)
- [x] `models.py` `Applicant` model mapping the existing table
- [x] Engine and Session configured with modern conventions
- [x] `orm_queries.py` repeats Questions 1, 4, 5, 8, 9 and one original question
- [x] No `text()` or raw cursors in the ORM work
- [x] Flask database reads use the ORM
- [x] SQL versus ORM comparison in this README

### Flask Webpage Functionality (20)
- [x] Connects to PostgreSQL through SQLAlchemy
- [x] Analysis results retrieved dynamically and displayed
- [x] Organized, readable, styled with CSS
- [x] Pull Data button functional and explained
- [x] Update Analysis refreshes results and handles an active scrape
- [x] Runs without major runtime errors

### Scraping and Data Refresh Integration (8)
- [x] Module 2 scraping reused
- [x] New records added without overwriting or corrupting existing data (`ON CONFLICT`, section 6.4)
- [x] Simultaneous operations prevented
- [x] Clear user-facing status and error messages

### Written Reflection: Data Limitations (7)
- [x] `limitations.pdf`: two substantive paragraphs, connected to at least one result

### Documentation, Screenshots, and Requirements (5)
- [x] Setup and run instructions for the database, SQL scripts, ORM, scraper, and Flask app
- [x] `requirements.txt` with all dependencies
- [x] Screenshots of raw SQL output, ORM output, and the running webpage

## 13. Submission Checklist

1. [x] `module_3.zip` containing the complete `module_3` folder, uploaded to Canvas
2. [x] Zip excludes `.env`, virtual environments, `__pycache__/`, and model weights
3. [x] `github.txt` with the SSH URL
4. [x] Final commit pushed to GitHub, matching the zip
