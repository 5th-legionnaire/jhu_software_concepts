"""
load_data.py: This program takes the cleaned applicant data
produced in Module 2 and loads it into a PostgreSQL database
(it may reuse existing functionality / move around content from clean.py and scrape.py).

EN 605.256 Modern Software Concepts in Python, Module 5.
Joshua Latz (jlatz1)
Written for Module 3; see the README for what Module 4 changed.

Contains:
    get_db_config():     connection settings from DATABASE_URL, or the PG* fallbacks
    create_connection(): open a connection using those settings
    execute_query():     run a single statement in its own transaction
    create_table():      create the applicants table and attach its column descriptions
    insert_records():    load records already in memory, in one transaction
    load_data():         read records back from a JSON file and load them into a PostgreSQL database

Usage (from module_4/):
    python3 src/load_data.py [path/to/llm_extend_applicant_data.json]
"""

import json
import os
import re
import sys
from datetime import datetime
from urllib import parse

import psycopg
from psycopg import OperationalError, sql
from dotenv import load_dotenv

load_dotenv()

# The bulk JSON lives in module_4/data/, one level above this file's src/.
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DATA_FILE = os.path.join(PROJECT_DIR, "data", "llm_extend_applicant_data.json")

PG_ENV_KEYS = {
    "host": "PGHOST",
    "port": "PGPORT",
    "dbname": "PGDATABASE",
    "user": "PGUSER",
    "password": "PGPASSWORD",
}


def _config_from_url(url):
    """Split a database URL into the keyword arguments psycopg.connect takes.

    Accepts the SQLAlchemy spelling with a driver suffix
    ("postgresql+psycopg://user:pass@host:5432/db") as well as a plain
    "postgresql://", so one variable serves both the psycopg code here and the
    ORM in models.py. The user name and password are percent-decoded, which is
    what makes a password containing "@" or "/" safe to carry in the URL.
    """
    parts = parse.urlsplit(url)
    return {
        "host": parts.hostname or "localhost",
        "port": str(parts.port or 5432),
        "dbname": parse.unquote(parts.path).lstrip("/") or None,
        "user": parse.unquote(parts.username or ""),
        "password": parse.unquote(parts.password or ""),
    }


def get_db_config(database_url=None):
    """Read connection settings from the environment (populated from .env if present).

    DATABASE_URL is the primary setting, so one variable configures both this
    module and the ORM, and a test can point the whole application at a
    disposable database. The PG* variables Module 3 used remain as a fallback,
    so an existing .env keeps working unchanged.

    Read at call time rather than import time, so importing this module
    (for example from a test) does not fail when nothing is set.

    Args:
        database_url: an explicit URL, as create_app() passes when a test
            overrides the configuration. Takes precedence over the environment.

    Returns:
        dict: host, port, dbname, user, and password for psycopg.connect().

    Raises:
        KeyError: when no URL is given or set and a PG* variable is missing.
    """
    url = database_url or os.environ.get("DATABASE_URL")
    if url:
        return _config_from_url(url)
    return {key: os.environ[name] for key, name in PG_ENV_KEYS.items()}


def create_connection(config):
    """Create a database connection to a config-defined PostgreSQL database.

    The connection runs in autocommit mode, and every write is wrapped in an
    explicit connection.transaction() block. In psycopg 3 that is the
    reliable way to get real BEGIN/COMMIT boundaries: without autocommit, a
    plain read opens an implicit transaction and a later transaction() block
    becomes a savepoint inside it rather than committing.
    """
    connection = None
    try:
        connection = psycopg.connect(
            dbname=config["dbname"],
            user=config["user"],
            password=config["password"],
            host=config["host"],
            port=config["port"],
            autocommit=True,
        )
        print("Connection to PostgreSQL DB successful")
    except OperationalError as e:
        print(f"The error '{e}' occurred")
    return connection


def execute_query(connection, query, params=None):
    """Execute a single query on the given database connection.

    connection.transaction() commits on success and rolls back on error.
    (In psycopg 3, `with connection:` would close the connection on exit,
    which is not what is wanted here.) The error is re-raised rather than
    swallowed, so a failed CREATE TABLE stops the run instead of surfacing
    later as a confusing insert error.
    """
    try:
        with connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute(query, params)
    except psycopg.Error as e:
        print(f"The error '{e}' occurred")
        raise


# Schema

CREATE_APPLICANTS_TABLE = """
CREATE TABLE IF NOT EXISTS applicants (
    p_id                      INTEGER PRIMARY KEY,
    program                   TEXT,
    comments                  TEXT,
    date_added                DATE,
    url                       TEXT UNIQUE,
    status                    TEXT,
    term                      TEXT,
    us_or_international       TEXT,
    gpa                       FLOAT,
    gre                       FLOAT,
    gre_v                     FLOAT,
    gre_aw                    FLOAT,
    degree                    TEXT,
    llm_generated_program     TEXT,
    llm_generated_university  TEXT,
    -- Additional columns, not in the assignment schema. Carried over from
    -- Module 2 so no parsed field is dropped on the way into the database.
    program_name              TEXT,
    university                TEXT,
    decision_date             TEXT
);
"""

# Column descriptions, directly from the Module 3 assignment schema.
# Stored in the catalog via COMMENT ON COLUMN; view with \d+ applicants.
COLUMN_DESCRIPTIONS = {
    "p_id": "Unique identifier",
    "program": "University and Department/Program",
    "comments": "Applicant comments",
    "date_added": "Date entry was added",
    "url": "Link to Grad Café entry",
    "status": "Admission status",
    "term": "Intended start term",
    "us_or_international": "Applicant nationality classification",
    "gpa": "Applicant GPA",
    "gre": "GRE Quantitative score",
    "gre_v": "GRE Verbal score",
    "gre_aw": "GRE Analytical Writing score",
    "degree": "Degree type",
    "llm_generated_program": "LLM-generated department/program",
    "llm_generated_university": "LLM-generated university",
    # Additional columns (descriptions are ours, not from the assignment).
    "program_name": "Program name alone, as presented by the site",
    "university": "University name alone, as presented by the site",
    "decision_date": "Date the decision was given, as presented by the site (no year)",
}

# Named placeholders so the loader can pass one dict per record.
# ON CONFLICT makes reruns skip rows already loaded instead of duplicating them.
INSERT_APPLICANT = """
INSERT INTO applicants (
    p_id, program, comments, date_added, url, status, term,
    us_or_international, gpa, gre, gre_v, gre_aw, degree,
    llm_generated_program, llm_generated_university,
    program_name, university, decision_date
) VALUES (
    %(p_id)s, %(program)s, %(comments)s, %(date_added)s, %(url)s,
    %(status)s, %(term)s, %(us_or_international)s, %(gpa)s, %(gre)s,
    %(gre_v)s, %(gre_aw)s, %(degree)s, %(llm_generated_program)s,
    %(llm_generated_university)s,
    %(program_name)s, %(university)s, %(decision_date)s
)
ON CONFLICT (p_id) DO NOTHING;
"""


def create_table(connection):
    """Create the applicants table and attach each column's description.

    Safe to run repeatedly: CREATE TABLE IF NOT EXISTS is a no-op on an
    existing table, and COMMENT ON simply overwrites. COMMENT ON cannot
    take bind parameters, so identifier and text are composed with
    psycopg.sql rather than string formatting.
    """
    execute_query(connection, CREATE_APPLICANTS_TABLE)
    for column, description in COLUMN_DESCRIPTIONS.items():
        execute_query(
            connection,
            sql.SQL("COMMENT ON COLUMN applicants.{} IS {}").format(
                sql.Identifier(column), sql.Literal(description)
            ),
        )


# Record conversion: Module 2 JSON -> applicants row

_RESULT_ID = re.compile(r"/result/(\d+)")
_NUMBER = re.compile(r"\d+(?:\.\d+)?")
_DATE_FORMATS = ("%b %d, %Y", "%B %d, %Y")


def _blank_to_none(value):
    """Map Module 2's empty-string missing marker to None (SQL NULL).

    Non-blank values are returned unmodified, so applicant-provided text
    is not trimmed or otherwise altered on the way in.
    """
    if value is None or str(value).strip() == "":
        return None
    return value


def _parse_score(value):
    """Strip the site's label prefix and return a float.

    'GPA 3.40' -> 3.4, 'GRE V 158' -> 158.0, 'GRE AW 4' -> 4.0.
    Returns None when the value is missing or holds no number.
    """
    text = _blank_to_none(value)
    if text is None:
        return None
    match = _NUMBER.search(str(text))
    return float(match.group()) if match else None


def _parse_date(value):
    """Parse 'Sep 12, 2026' (or the older 'Added on March 31, 2024') into a date."""
    text = _blank_to_none(value)
    if text is None:
        return None
    text = str(text).strip().removeprefix("Added on ").strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _p_id_from_url(url):
    """Return the Grad Cafe result id from a permalink, e.g. .../result/1020482 -> 1020482."""
    match = _RESULT_ID.search(url or "")
    return int(match.group(1)) if match else None


def _prepare_record(record):
    """Convert one Module 2 record (its JSON keys) into an applicants row (column names)."""
    url = _blank_to_none(record.get("url"))
    return {
        "p_id": _p_id_from_url(url),
        "program": _blank_to_none(record.get("program")),
        "comments": _blank_to_none(record.get("comments")),
        "date_added": _parse_date(record.get("date_added")),
        "url": url,
        "status": _blank_to_none(record.get("status")),
        "term": _blank_to_none(record.get("term")),
        "us_or_international": _blank_to_none(record.get("US/International")),
        "gpa": _parse_score(record.get("GPA")),
        "gre": _parse_score(record.get("GRE")),
        "gre_v": _parse_score(record.get("GRE V")),
        "gre_aw": _parse_score(record.get("GRE AW")),
        "degree": _blank_to_none(record.get("Degree")),
        "llm_generated_program": _blank_to_none(record.get("llm-generated-program")),
        "llm_generated_university": _blank_to_none(record.get("llm-generated-university")),
        "program_name": _blank_to_none(record.get("program_name")),
        "university": _blank_to_none(record.get("university")),
        "decision_date": _blank_to_none(record.get("decision_date")),
    }


def _read_records(path):
    """Read the Module 2 output: a JSON array of applicant records."""
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, list):
        raise ValueError(f"{path}: expected a JSON array of records")
    return data


def _count_rows(connection):
    """Return the current number of rows in applicants."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM applicants;")
        return cursor.fetchone()[0]


# Loader

def insert_records(connection, records):
    """Load records already held in memory into the applicants table.

    All inserts run in one transaction: either every record lands or none
    does, so a failure part way through leaves no partial write. psycopg 3's
    executemany() pipelines the statements, so 30,000 rows need no manual
    batching. ON CONFLICT (p_id) DO NOTHING makes a repeated pull a no-op
    rather than a duplicate, which is the uniqueness policy the analysis
    relies on.

    Args:
        connection: an open psycopg connection, as returned by create_connection().
        records: Module 2 applicant records, using their JSON key names.

    Returns:
        int: rows newly inserted, which is 0 when every record was already present.
    """
    rows, skipped = [], 0
    for record in records:
        row = _prepare_record(record)
        if row["p_id"] is None:  # no result id means no primary key
            skipped += 1
            continue
        rows.append(row)

    before = _count_rows(connection)
    with connection.transaction():
        with connection.cursor() as cursor:
            cursor.executemany(INSERT_APPLICANT, rows)
    inserted = _count_rows(connection) - before

    print(
        f"Read {len(records)} records: {inserted} inserted, "
        f"{len(rows) - inserted} already present, "
        f"{skipped} skipped (no result id in url)"
    )
    return inserted


def load_data(connection, path=DEFAULT_DATA_FILE):
    """Read records back from a JSON file and load them into a PostgreSQL database.

    Args:
        connection: an open psycopg connection.
        path: a JSON array of Module 2 applicant records.

    Returns:
        int: rows newly inserted, 0 on a rerun against an already-loaded table.
    """
    return insert_records(connection, _read_records(path))


def main():
    """Create the table if needed, then load the Module 2 data."""
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_DATA_FILE
    connection = create_connection(get_db_config())
    if connection is None:
        sys.exit(1)
    try:
        create_table(connection)
        load_data(connection, path)
    finally:
        connection.close()


if __name__ == "__main__":  # pragma: no cover - command line entry point
    main()