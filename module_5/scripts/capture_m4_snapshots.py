"""capture_m4_snapshots.py: record Module 4's query behavior before Module 5 changes it.

EN 605.256 Modern Software Concepts in Python, Module 5.
Joshua Latz (jlatz1)

Run once, in Phase 0, against the frozen Module 4 source tree. The two files it
writes are the fixed points the Module 5 refactor is measured against:

    tests/snapshots/m4_run_all.txt   query_data.run_all() over the full committed
                                     dataset (the parity test in Phase 3)
    tests/snapshots/m4_orm_sql.txt   compiled PostgreSQL text and bound parameters
                                     of every orm_queries *_stmt() builder (the
                                     CHG-16 check in Phase 6)

The full dataset is used rather than the two conftest rows because two rows
leave Q5, Q8, and Q9 at zero, which would let a broken regex or range bind pass
the parity test unnoticed.

Contains:
    Snapshot writers: capture_run_all(), capture_orm_sql()
    Entry point:      main()

Usage (from module_5/, with a disposable database in TEST_DATABASE_URL):
    python scripts/capture_m4_snapshots.py ../module_4/src
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MODULE_DIR = os.path.dirname(HERE)
SNAPSHOT_DIR = os.path.join(MODULE_DIR, "tests", "snapshots")
DATA_FILE = os.path.join(MODULE_DIR, "data", "llm_extend_applicant_data.json")


def capture_run_all(database_url):
    """Seed the disposable database with the full dataset and return run_all() lines.

    Args:
        database_url: URL of a database whose applicants table may be truncated.

    Returns:
        list[str]: run_all() output lines.
    """
    # Imported here, not at the top, so they resolve from the tree main() put on sys.path.
    import load_data
    import query_data

    connection = load_data.create_connection(load_data.get_db_config(database_url))
    if connection is None:
        sys.exit("Database unreachable; set TEST_DATABASE_URL to a disposable database.")
    try:
        load_data.create_table(connection)
        load_data.execute_query(connection, "TRUNCATE applicants")
        load_data.insert_records(connection, load_data._read_records(DATA_FILE))
        with connection.cursor() as cursor:
            lines = query_data.run_all(cursor)
        load_data.execute_query(connection, "TRUNCATE applicants")
    finally:
        connection.close()
    return lines


def capture_orm_sql():
    """Return the compiled SQL of every orm_queries *_stmt() builder, in name order.

    Returns:
        list[str]: one block per builder, headed by its name.
    """
    import orm_queries

    blocks = []
    for name in sorted(n for n in dir(orm_queries) if n.endswith("_stmt")):
        blocks.append(f"-- {name}\n{orm_queries._sql(getattr(orm_queries, name)())}")
    return blocks


def main():
    """Capture both snapshots from the source tree named on the command line."""
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    database_url = os.environ.get("TEST_DATABASE_URL")
    if not database_url:
        sys.exit("TEST_DATABASE_URL is not set.")
    # The script imports the frozen Module 4 modules, not Module 5's, so the
    # snapshots describe the baseline even after src/ starts changing.
    sys.path.insert(0, os.path.abspath(sys.argv[1]))
    os.makedirs(SNAPSHOT_DIR, exist_ok=True)
    with open(os.path.join(SNAPSHOT_DIR, "m4_run_all.txt"), "w", encoding="utf-8") as out:
        out.write("\n".join(capture_run_all(database_url)) + "\n")
    with open(os.path.join(SNAPSHOT_DIR, "m4_orm_sql.txt"), "w", encoding="utf-8") as out:
        out.write("\n\n".join(capture_orm_sql()) + "\n")
    print(f"Snapshots written to {SNAPSHOT_DIR}")


if __name__ == "__main__":
    main()
