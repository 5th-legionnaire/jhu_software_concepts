"""
load_data.py: This program takes the cleaned applicant data
produced in Module 2 and loads it into a PostgreSQL database
(it may reuse existing functionality / move around content from clean.py and scrape.py).

EN 605.256 Modern Software Concepts in Python, Module 5.
Joshua Latz (jlatz1)
Written for Module 3; see the README for what Modules 4 and 5 changed.

Contains:
    get_db_config():     connection settings for a role, from an explicit URL,
                         DATABASE_URL, or the DB_* variables
    create_connection(): open a connection using those settings, logging a
                         sanitized message on failure
    COLUMNS:             the one list of table columns that the DDL and the INSERT are built from
    execute_query():     run a single composed statement in its own transaction
    build_create_table(), build_insert(), build_count():
                         compose the statements, touching no database
    create_table():      create the applicants table and attach its column descriptions (owner only)
    insert_records():    load records already in memory, in one transaction
    load_data():         read records back from a JSON file and load them into a PostgreSQL database

Usage (from module_5/):
    python3 src/load_data.py [path/to/llm_extend_applicant_data.json]
"""

import json
import logging
import os
import re
import sys
from datetime import datetime
from urllib import parse

import psycopg
from psycopg import OperationalError, sql
from dotenv import load_dotenv

from db_safety import clamp_limit

load_dotenv()

logger = logging.getLogger(__name__)

# The bulk JSON lives in module_5/data/, one level above this file's src/.
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DATA_FILE = os.path.join(PROJECT_DIR, "data", "llm_extend_applicant_data.json")

# Where the server is and which database to open, shared by every role.
DB_LOCATION_ENV = {
    "host": "DB_HOST",
    "port": "DB_PORT",
    "dbname": "DB_NAME",
}

# Who connects. The runtime account is least-privilege; the owner account does
# schema setup and the bulk load only (see sql/roles.sql). Keeping them under
# different variable names means a run cannot silently use the wrong account.
ROLE_ENV = {
    "app": {"user": "DB_USER", "password": "DB_PASSWORD"},
    "owner": {"user": "DB_OWNER_USER", "password": "DB_OWNER_PASSWORD"},
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


def _require(name):
    """Return the environment variable's value, naming the variable if it is unset.

    Raises:
        KeyError: carrying the variable's name and never any value.
    """
    try:
        return os.environ[name]
    except KeyError:
        raise KeyError(f"{name} is not set; see .env.example") from None


def get_db_config(database_url=None, role="app"):
    """Read connection settings for a role (populated from .env if present).

    Precedence, highest first:
        1. the explicit ``database_url`` argument, as create_app() passes when
           a test overrides the configuration;
        2. the DATABASE_URL environment variable, an override for CI and tests;
        3. DB_HOST, DB_PORT, and DB_NAME, plus DB_USER and DB_PASSWORD for the
           ``app`` role, or DB_OWNER_USER and DB_OWNER_PASSWORD for ``owner``.

    Module 3's PG* variables are no longer read: two parallel settings would
    let a misconfigured run quietly use the wrong account.

    Read at call time rather than import time, so importing this module
    (for example from a test) does not fail when nothing is set.

    Args:
        database_url: an explicit URL. Takes precedence over the environment.
        role: ``"app"`` for the runtime account, ``"owner"`` for schema setup
            and bulk loading.

    Returns:
        dict: host, port, dbname, user, and password for psycopg.connect().

    Raises:
        ValueError: when ``role`` is not a known role.
        KeyError: when no URL is given or set and a variable is missing. The
            message names the variable and never reveals a value.
    """
    if role not in ROLE_ENV:
        raise ValueError(f"Unknown database role {role!r}; expected one of {sorted(ROLE_ENV)}")
    url = database_url or os.environ.get("DATABASE_URL")
    if url:
        return _config_from_url(url)
    names = {**DB_LOCATION_ENV, **ROLE_ENV[role]}
    return {key: _require(name) for key, name in names.items()}


def create_connection(config):
    """Create a database connection to a config-defined PostgreSQL database.

    The connection runs in autocommit mode, and every write is wrapped in an
    explicit connection.transaction() block. In psycopg 3 that is the
    reliable way to get real BEGIN/COMMIT boundaries: without autocommit, a
    plain read opens an implicit transaction and a later transaction() block
    becomes a savepoint inside it rather than committing.

    On failure this logs the exception's type and a fixed hint, not its text.
    libpq error text can echo the host, port, and user name, which would put
    connection details into terminals and CI logs.

    Returns:
        psycopg.Connection, or None when the connection could not be opened.
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
    except OperationalError as error:
        logger.error(
            "Could not connect to the database (%s). Check that PostgreSQL is "
            "running and that the DB_* settings in .env, or DATABASE_URL, are correct.",
            type(error).__name__,
        )
    return connection


def execute_query(connection, query, params=None):
    """Execute a single composed statement on the given database connection.

    ``query`` must be a psycopg ``sql.Composable`` (``sql.SQL``, ``Composed``).
    A bare string is refused, so a statement cannot reach the driver unless it
    was built with the composition API (CHG-05). This is the one place the
    module executes anything.

    connection.transaction() commits on success and rolls back on error.
    (In psycopg 3, `with connection:` would close the connection on exit,
    which is not what is wanted here.) The error is re-raised rather than
    swallowed, so a failed CREATE TABLE stops the run instead of surfacing
    later as a confusing insert error.

    Raises:
        TypeError: when ``query`` is not a ``sql.Composable``.
    """
    if not isinstance(query, sql.Composable):
        raise TypeError("execute_query needs a psycopg sql.Composable, not a bare string")
    try:
        with connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute(query, params)
    except psycopg.Error as e:
        print(f"The error '{e}' occurred")
        raise


# Schema

TABLE = sql.Identifier("applicants")

# The columns of the applicants table, in order, with their SQL types. The
# CREATE TABLE statement and the INSERT are both generated from this one tuple
# (CHG-06), so the two cannot drift apart. The first group is the Module 3
# assignment schema; the last three are additional columns carried over from
# Module 2 so no parsed field is dropped on the way into the database.
COLUMNS = (
    ("p_id", "INTEGER PRIMARY KEY"),
    ("program", "TEXT"),
    ("comments", "TEXT"),
    ("date_added", "DATE"),
    ("url", "TEXT UNIQUE"),
    ("status", "TEXT"),
    ("term", "TEXT"),
    ("us_or_international", "TEXT"),
    ("gpa", "FLOAT"),
    ("gre", "FLOAT"),
    ("gre_v", "FLOAT"),
    ("gre_aw", "FLOAT"),
    ("degree", "TEXT"),
    ("llm_generated_program", "TEXT"),
    ("llm_generated_university", "TEXT"),
    ("program_name", "TEXT"),
    ("university", "TEXT"),
    ("decision_date", "TEXT"),
)
COLUMN_NAMES = tuple(name for name, _type in COLUMNS)
PRIMARY_KEY = COLUMN_NAMES[0]


def build_create_table():
    """Compose CREATE TABLE IF NOT EXISTS for the applicants table.

    Returns:
        sql.Composed: the statement. No database is touched.
    """
    definitions = sql.SQL(", ").join(
        sql.SQL("{name} {type}").format(name=sql.Identifier(name), type=sql.SQL(column_type))
        for name, column_type in COLUMNS
    )
    return sql.SQL("CREATE TABLE IF NOT EXISTS {table} ({definitions})").format(
        table=TABLE, definitions=definitions)


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

def build_insert():
    """Compose the INSERT, with one named placeholder per column.

    Named placeholders let the loader pass one dict per record. ON CONFLICT
    makes reruns skip rows already loaded instead of duplicating them.

    Returns:
        sql.Composed: the statement. No database is touched.
    """
    return sql.SQL(
        "INSERT INTO {table} ({columns}) VALUES ({values}) ON CONFLICT ({key}) DO NOTHING"
    ).format(
        table=TABLE,
        columns=sql.SQL(", ").join(sql.Identifier(name) for name in COLUMN_NAMES),
        values=sql.SQL(", ").join(sql.Placeholder(name) for name in COLUMN_NAMES),
        key=sql.Identifier(PRIMARY_KEY),
    )


def build_count():
    """Compose the row count, limited to one output row.

    Returns:
        tuple[sql.Composed, dict]: the statement and its parameters.
    """
    statement = sql.SQL("SELECT COUNT(*) FROM {table} LIMIT {limit}").format(
        table=TABLE, limit=sql.Placeholder("limit"))
    return statement, {"limit": clamp_limit(1)}


def create_table(connection):
    """Create the applicants table and attach each column's description.

    Safe to run repeatedly: CREATE TABLE IF NOT EXISTS is a no-op on an
    existing table, and COMMENT ON simply overwrites. COMMENT ON cannot
    take bind parameters, so identifier and text are composed with
    psycopg.sql rather than string formatting.
    """
    execute_query(connection, build_create_table())
    for column, description in COLUMN_DESCRIPTIONS.items():
        execute_query(
            connection,
            sql.SQL("COMMENT ON COLUMN {table}.{column} IS {text}").format(
                table=TABLE, column=sql.Identifier(column), text=sql.Literal(description)
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
    statement, params = build_count()
    with connection.cursor() as cursor:
        cursor.execute(statement, params)
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
            cursor.executemany(build_insert(), rows)
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
    """Create the table if needed, then load the Module 2 data.

    Connects as the owner role: schema setup and the bulk load are the owner's
    job, and the runtime account has neither privilege (CHG-11, CHG-12).
    """
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_DATA_FILE
    connection = create_connection(get_db_config(role="owner"))
    if connection is None:
        sys.exit(1)
    try:
        create_table(connection)
        load_data(connection, path)
    finally:
        connection.close()


if __name__ == "__main__":  # pragma: no cover - command line entry point
    main()
