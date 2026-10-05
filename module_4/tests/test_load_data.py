"""load_data.py: connection config, schema, record conversion, and the loader.

Rubric: "Test Organization, Markers, and Coverage" (100% coverage of src/).
Most of this module runs already, indirectly, through insert_records() calls
in other test files, but several branches only a dedicated test reaches: the
PG* fallback when DATABASE_URL is unset, a failed connection, a failed
statement, the "blank value becomes NULL" conversion for each field type, and
load_data()/main() themselves, which nothing else in the suite calls.
"""

import datetime
import json

import psycopg
import pytest

import load_data as ld

pytestmark = pytest.mark.db


# --- get_db_config: the PG* fallback ----------------------------------------

def test_get_db_config_falls_back_to_pg_star_variables(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("PGHOST", "fallback-host")
    monkeypatch.setenv("PGPORT", "5433")
    monkeypatch.setenv("PGDATABASE", "fallback-db")
    monkeypatch.setenv("PGUSER", "fallback-user")
    monkeypatch.setenv("PGPASSWORD", "fallback-pass")

    assert ld.get_db_config() == {
        "host": "fallback-host", "port": "5433", "dbname": "fallback-db",
        "user": "fallback-user", "password": "fallback-pass",
    }


# --- create_connection: the failure path ------------------------------------

def test_create_connection_returns_none_on_failure():
    """Port 1 is privileged and essentially never listening: a fast, reliable refusal."""
    bad_config = {"host": "localhost", "port": "1", "dbname": "x",
                  "user": "x", "password": "x"}
    assert ld.create_connection(bad_config) is None


# --- execute_query: the failure path ----------------------------------------

def test_execute_query_reraises_and_does_not_swallow_the_error(clean_db, db_url):
    connection = ld.create_connection(ld.get_db_config(db_url))
    try:
        with pytest.raises(psycopg.Error):
            ld.execute_query(connection, "SELECT * FROM no_such_table_xyz;")
    finally:
        connection.close()


# --- _prepare_record: blank-to-None conversion, by field type --------------

def test_prepare_record_maps_blank_fields_to_none():
    """A blank url means no p_id at all, which is what makes the row unloadable."""
    record = {key: "" for key in (
        "url", "program", "date_added", "status", "term", "US/International",
        "GPA", "GRE", "GRE V", "GRE AW", "Degree", "llm-generated-program",
        "llm-generated-university", "program_name", "university", "decision_date")}
    record["comments"] = None

    row = ld._prepare_record(record)

    assert row["p_id"] is None
    assert row["url"] is None
    assert row["program"] is None
    assert row["comments"] is None
    assert row["date_added"] is None
    assert row["gpa"] is None


def test_prepare_record_returns_none_for_an_unparseable_date():
    record = {"url": "https://www.thegradcafe.com/result/1", "date_added": "not a date"}
    assert ld._prepare_record(record)["date_added"] is None


def test_prepare_record_parses_the_added_on_date_format():
    """The older "Added on <date>" format, carried over from Module 2."""
    record = {"url": "https://www.thegradcafe.com/result/1",
              "date_added": "Added on March 31, 2024"}
    assert ld._prepare_record(record)["date_added"] == datetime.date(2024, 3, 31)


# --- _read_records: the file-reading half of load_data() -------------------

def test_read_records_returns_the_json_array(tmp_path):
    path = tmp_path / "records.json"
    path.write_text(json.dumps([{"url": "x"}]), encoding="utf-8")
    assert ld._read_records(str(path)) == [{"url": "x"}]


def test_read_records_rejects_a_non_array_json_file(tmp_path):
    path = tmp_path / "records.json"
    path.write_text(json.dumps({"not": "a list"}), encoding="utf-8")
    with pytest.raises(ValueError, match="expected a JSON array"):
        ld._read_records(str(path))


# --- insert_records: the skipped-record branch ------------------------------

def test_insert_records_skips_rows_with_no_result_id(clean_db, db_url):
    connection = ld.create_connection(ld.get_db_config(db_url))
    try:
        inserted = ld.insert_records(connection, [{"url": "", "program": "no id"}])
    finally:
        connection.close()
    assert inserted == 0


# --- load_data: the public file-reading wrapper -----------------------------

def test_load_data_reads_a_file_and_loads_it(clean_db, fake_rows, db_url, tmp_path):
    path = tmp_path / "records.json"
    path.write_text(json.dumps(fake_rows), encoding="utf-8")
    connection = ld.create_connection(ld.get_db_config(db_url))
    try:
        inserted = ld.load_data(connection, str(path))
    finally:
        connection.close()
    assert inserted == len(fake_rows)


# --- main: both branches ----------------------------------------------------

def test_main_exits_when_the_database_is_unreachable(monkeypatch):
    monkeypatch.setattr(ld, "create_connection", lambda config: None)
    with pytest.raises(SystemExit):
        ld.main()


def test_main_creates_the_table_and_loads_the_given_file(
        monkeypatch, clean_db, fake_rows, db_url, tmp_path, capsys):
    path = tmp_path / "records.json"
    path.write_text(json.dumps(fake_rows), encoding="utf-8")
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setattr("sys.argv", ["load_data.py", str(path)])

    ld.main()

    assert f"{len(fake_rows)} inserted" in capsys.readouterr().out
