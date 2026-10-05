"""Raw SQL query functions: query_data.py's independent path to the analyses.

Rubric: "Test Organization, Markers, and Coverage" (100% coverage of src/).
app.py reads results through orm_queries.py (the ORM path), never through
this module, so nothing else in the suite exercises it. Run against a real
database rather than a fake cursor: that proves the SQL text itself still
executes correctly against PostgreSQL, not just that Python unpacks a row
into a dict. fake_rows gives small, known, hand-checkable results for every
question.
"""

import pytest

import query_data as qd
from load_data import create_connection, get_db_config, insert_records

pytestmark = pytest.mark.db


@pytest.fixture
def cursor(clean_db, fake_rows, db_url):
    """A real psycopg cursor, over a database seeded with fake_rows."""
    connection = create_connection(get_db_config(db_url))
    insert_records(connection, fake_rows)
    with connection.cursor() as cur:
        yield cur
    connection.close()


# fake_rows: one Masters, American, JHU Computer Science applicant (GPA 3.80),
# one PhD, International, Stanford Electrical Engineering applicant (GPA
# 3.90). Both Fall 2026, both Accepted. Chosen in conftest.py to give every
# formatter something non-trivial to round; here they give every question a
# small, hand-checkable answer.

def test_q1_counts_fall_2026_entries(cursor):
    assert qd.q1(cursor) == {"count": 2}


def test_q2_percent_international(cursor):
    result = qd.q2(cursor)
    assert result["international"] == 1
    assert result["classified"] == 2
    assert result["pct"] == pytest.approx(50.0)


def test_q3_averages_only_on_scale_values(cursor):
    result = qd.q3(cursor)
    assert result["n_gpa"] == 2
    assert result["avg_gpa"] == pytest.approx((3.80 + 3.90) / 2)


def test_q4_average_gpa_american_fall_2026(cursor):
    result = qd.q4(cursor)
    assert result["n"] == 1
    assert result["avg_gpa"] == pytest.approx(3.80)


def test_q5_fall_2025_percentage_is_null_with_no_fall_2025_data(cursor):
    """Neither fake row is Fall 2025, so the percentage is NULL, not zero."""
    assert qd.q5(cursor) == {"accepted": 0, "total": 0, "pct": None}


def test_q6_average_gpa_accepted_fall_2026(cursor):
    result = qd.q6(cursor)
    assert result["n"] == 2
    assert result["avg_gpa"] == pytest.approx((3.80 + 3.90) / 2)


def test_q7_jhu_masters_computer_science(cursor):
    assert qd.q7(cursor) == {"count": 1}


def test_q8_and_q9_agree_when_the_llm_fields_match_the_original(cursor):
    """Neither row is a CS PhD at the four universities, by either field set."""
    assert qd.q8(cursor) == {"count": 0}
    assert qd.q9(cursor) == {"original": 0, "llm": 0, "difference": 0}


def test_uq1_groups_by_whether_gpa_was_reported(cursor):
    """Both rows report a usable GPA, so there is only the one group."""
    assert qd.uq1(cursor) == [
        {"group": "Reported GPA", "entries": 2, "accepted": 2, "pct": pytest.approx(100.0)}
    ]


def test_uq2_groups_by_degree_and_nationality(cursor):
    result = qd.uq2(cursor)
    groups = {(row["degree"], row["nationality"]) for row in result}
    assert groups == {("Masters", "American"), ("PhD", "International")}
    assert all(row["pct"] == pytest.approx(100.0) for row in result)


def test_run_all_returns_formatted_lines_for_every_question(cursor):
    text = "\n".join(qd.run_all(cursor))
    assert "Q1  Fall 2026 applicant count: 2" in text
    assert "UQ1" in text
    assert "UQ2" in text


def test_main_prints_run_all_output(capsys, monkeypatch, clean_db, db_url):
    """main()'s own connect-run-print path, not the cursor fixture above."""
    monkeypatch.setenv("DATABASE_URL", db_url)
    qd.main()
    assert "Q1" in capsys.readouterr().out


def test_main_exits_when_database_is_unreachable(monkeypatch):
    monkeypatch.setattr(qd, "create_connection", lambda config: None)
    with pytest.raises(SystemExit):
        qd.main()
