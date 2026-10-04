"""
query_data.py: This program answers the Module 3 analysis questions about
Grad Cafe submissions using SQL queries executed through psycopg.

EN 605.256 Modern Software Concepts in Python, Module 4.
Joshua Latz (jlatz1)
Written for Module 3 and carried over unchanged.

Contains:
    Validity ranges:  GPA_RANGE, GRE_Q_RANGE, GRE_V_RANGE, GRE_AW_RANGE
    Formatters:       fmt_count(), fmt_pct(), fmt_avg(), fmt_diff()
    Questions:        q1() to q9(), q10() and q11() (the two original questions)
    Output:           run_all(), main()

Every analysis is expressed in SQL. Python only executes the queries and
formats the results. The SQL strings are module-level constants so the exact
text that runs is the text quoted in query_results.pdf.

Usage (from module_4/):
    python3 src/query_data.py
"""

from load_data import create_connection, get_db_config

# Validity ranges (see "Validity ranges" in the README)
#
# Applied inside the averaging queries only; the table holds every value as
# reported. A value outside its metric's scale does not "provide" that metric,
# so it is excluded from that average, and the exclusion count is reported.
# Imported by orm_queries.py so the SQL and ORM answers use identical filters.
GPA_RANGE = (0.0, 4.0)        # 134 values on 4.33, 10-point, or other scales
GRE_Q_RANGE = (130.0, 170.0)  # the site's GRE field mostly holds 260-340 totals
GRE_V_RANGE = (130.0, 170.0)
GRE_AW_RANGE = (0.0, 6.0)

# Matching patterns, PostgreSQL case-insensitive regex (~*).
# \m and \M are PostgreSQL's word-start and word-end anchors, so "jhu" and
# "mit" match as whole words and not inside longer words.
JHU_PATTERN = r"johns? hopkins|\mjhu\M"
CS_PATTERN = r"computer science"
Q8_UNIVERSITY_PATTERN = (
    r"georgetown|massachusetts institute of technology|\mmit\M"
    r"|stanford|carnegie mellon|\mcmu\M"
)


# Formatters (assignment output formatting rules)

def fmt_count(value):
    """Whole number with thousands separators, e.g. 19,290."""
    return f"{value:,}"


def fmt_pct(value):
    """Two decimal places and a percent sign, e.g. 50.09%."""
    return "n/a" if value is None else f"{value:.2f}%"


def fmt_avg(value):
    """Two decimal places, e.g. 3.79."""
    return "n/a" if value is None else f"{value:.2f}"


def fmt_diff(value):
    """Signed whole number, e.g. +3, -2, 0."""
    return f"{value:+d}" if value else "0"


# SQL

Q1_SQL = """
SELECT COUNT(*)
FROM applicants
WHERE LOWER(term) = 'fall 2026';
"""

Q2_SQL = """
SELECT
    COUNT(*) FILTER (WHERE LOWER(us_or_international) = 'international') AS international,
    COUNT(*) AS classified,
    100.0 * COUNT(*) FILTER (WHERE LOWER(us_or_international) = 'international')
          / NULLIF(COUNT(*), 0) AS pct_international
FROM applicants
WHERE us_or_international IS NOT NULL
  AND TRIM(us_or_international) <> '';
"""

Q3_SQL = f"""
SELECT
    AVG(gpa)    FILTER (WHERE gpa    BETWEEN {GPA_RANGE[0]}    AND {GPA_RANGE[1]})    AS avg_gpa,
    AVG(gre)    FILTER (WHERE gre    BETWEEN {GRE_Q_RANGE[0]}  AND {GRE_Q_RANGE[1]})  AS avg_gre_q,
    AVG(gre_v)  FILTER (WHERE gre_v  BETWEEN {GRE_V_RANGE[0]}  AND {GRE_V_RANGE[1]})  AS avg_gre_v,
    AVG(gre_aw) FILTER (WHERE gre_aw BETWEEN {GRE_AW_RANGE[0]} AND {GRE_AW_RANGE[1]}) AS avg_gre_aw,
    COUNT(gpa)    FILTER (WHERE gpa    BETWEEN {GPA_RANGE[0]}    AND {GPA_RANGE[1]})    AS n_gpa,
    COUNT(gre)    FILTER (WHERE gre    BETWEEN {GRE_Q_RANGE[0]}  AND {GRE_Q_RANGE[1]})  AS n_gre_q,
    COUNT(gre_v)  FILTER (WHERE gre_v  BETWEEN {GRE_V_RANGE[0]}  AND {GRE_V_RANGE[1]})  AS n_gre_v,
    COUNT(gre_aw) FILTER (WHERE gre_aw BETWEEN {GRE_AW_RANGE[0]} AND {GRE_AW_RANGE[1]}) AS n_gre_aw,
    COUNT(gpa)    - COUNT(gpa)    FILTER (WHERE gpa    BETWEEN {GPA_RANGE[0]}    AND {GPA_RANGE[1]})    AS x_gpa,
    COUNT(gre)    - COUNT(gre)    FILTER (WHERE gre    BETWEEN {GRE_Q_RANGE[0]}  AND {GRE_Q_RANGE[1]})  AS x_gre_q,
    COUNT(gre_v)  - COUNT(gre_v)  FILTER (WHERE gre_v  BETWEEN {GRE_V_RANGE[0]}  AND {GRE_V_RANGE[1]})  AS x_gre_v,
    COUNT(gre_aw) - COUNT(gre_aw) FILTER (WHERE gre_aw BETWEEN {GRE_AW_RANGE[0]} AND {GRE_AW_RANGE[1]}) AS x_gre_aw
FROM applicants;
"""

Q4_SQL = f"""
SELECT AVG(gpa), COUNT(gpa)
FROM applicants
WHERE LOWER(term) = 'fall 2026'
  AND LOWER(us_or_international) = 'american'
  AND gpa BETWEEN {GPA_RANGE[0]} AND {GPA_RANGE[1]};
"""

Q5_SQL = """
SELECT
    COUNT(*) FILTER (WHERE LOWER(status) = 'accepted') AS accepted,
    COUNT(*) AS total,
    100.0 * COUNT(*) FILTER (WHERE LOWER(status) = 'accepted')
          / NULLIF(COUNT(*), 0) AS pct_accepted
FROM applicants
WHERE LOWER(term) = 'fall 2025';
"""

Q6_SQL = f"""
SELECT AVG(gpa), COUNT(gpa)
FROM applicants
WHERE LOWER(term) = 'fall 2026'
  AND LOWER(status) = 'accepted'
  AND gpa BETWEEN {GPA_RANGE[0]} AND {GPA_RANGE[1]};
"""

# Original downloaded fields: program holds "Program, University" as the
# site presents it, so both university and program are matched within it.
Q7_SQL = f"""
SELECT COUNT(*)
FROM applicants
WHERE program ~* '{JHU_PATTERN}'
  AND program ~* '{CS_PATTERN}'
  AND LOWER(degree) = 'masters';
"""

Q8_SQL = f"""
SELECT COUNT(*)
FROM applicants
WHERE LOWER(term) = 'fall 2026'
  AND LOWER(status) = 'accepted'
  AND LOWER(degree) = 'phd'
  AND program ~* '{CS_PATTERN}'
  AND program ~* '{Q8_UNIVERSITY_PATTERN}';
"""

# Same restrictions as Q8, with university and program identified from the
# LLM fields. Term, degree, and status stay on the original fields.
Q9_SQL = f"""
SELECT COUNT(*)
FROM applicants
WHERE LOWER(term) = 'fall 2026'
  AND LOWER(status) = 'accepted'
  AND LOWER(degree) = 'phd'
  AND llm_generated_program ~* '{CS_PATTERN}'
  AND llm_generated_university ~* '{Q8_UNIVERSITY_PATTERN}';
"""

# User created question 1: do applicants who report a GPA post acceptances at a
# different rate from those who do not? A direct measure of whether
# self-reporting correlates with outcome (see limitations.pdf).
UQ1_SQL = f"""
SELECT
    CASE WHEN gpa BETWEEN {GPA_RANGE[0]} AND {GPA_RANGE[1]}
         THEN 'Reported GPA' ELSE 'No usable GPA' END AS gpa_reported,
    COUNT(*) AS entries,
    COUNT(*) FILTER (WHERE LOWER(status) = 'accepted') AS accepted,
    100.0 * COUNT(*) FILTER (WHERE LOWER(status) = 'accepted')
          / NULLIF(COUNT(*), 0) AS pct_accepted
FROM applicants
WHERE LOWER(term) = 'fall 2026'
GROUP BY 1
ORDER BY 1 DESC;
"""

# User created question 2: how do acceptance rates for Fall 2026 differ between
# American and International applicants, for PhD and Masters programs?
UQ2_SQL = """
SELECT
    CASE LOWER(degree) WHEN 'phd' THEN 'PhD' ELSE 'Masters' END AS degree_group,
    CASE LOWER(us_or_international) WHEN 'american' THEN 'American'
         ELSE 'International' END AS nationality,
    COUNT(*) AS entries,
    COUNT(*) FILTER (WHERE LOWER(status) = 'accepted') AS accepted,
    100.0 * COUNT(*) FILTER (WHERE LOWER(status) = 'accepted')
          / NULLIF(COUNT(*), 0) AS pct_accepted
FROM applicants
WHERE LOWER(term) = 'fall 2026'
  AND LOWER(degree) IN ('phd', 'masters')
  AND LOWER(us_or_international) IN ('american', 'international')
GROUP BY 1, 2
ORDER BY 1 DESC, 2;
"""


# Question functions: each runs its SQL and returns plain Python values

def _one(cursor, query):
    """Execute a query and return its single result row."""
    cursor.execute(query)
    return cursor.fetchone()


def q1(cursor):
    """Fall 2026 applicant count."""
    return {"count": _one(cursor, Q1_SQL)[0]}


def q2(cursor):
    """Percentage international among entries with a nationality classification."""
    international, classified, pct = _one(cursor, Q2_SQL)
    return {"international": international, "classified": classified, "pct": pct}


def q3(cursor):
    """Average GPA and GRE scores, each over applicants providing that metric."""
    row = _one(cursor, Q3_SQL)
    keys = ("avg_gpa", "avg_gre_q", "avg_gre_v", "avg_gre_aw",
            "n_gpa", "n_gre_q", "n_gre_v", "n_gre_aw",
            "x_gpa", "x_gre_q", "x_gre_v", "x_gre_aw")
    return dict(zip(keys, row))


def q4(cursor):
    """Average GPA of American Fall 2026 applicants."""
    avg, n = _one(cursor, Q4_SQL)
    return {"avg_gpa": avg, "n": n}


def q5(cursor):
    """Fall 2025 acceptance percentage."""
    accepted, total, pct = _one(cursor, Q5_SQL)
    return {"accepted": accepted, "total": total, "pct": pct}


def q6(cursor):
    """Average GPA of accepted Fall 2026 applicants."""
    avg, n = _one(cursor, Q6_SQL)
    return {"avg_gpa": avg, "n": n}


def q7(cursor):
    """JHU Masters in Computer Science entries, original fields."""
    return {"count": _one(cursor, Q7_SQL)[0]}


def q8(cursor):
    """Fall 2026 CS PhD acceptances at the four universities, original fields."""
    return {"count": _one(cursor, Q8_SQL)[0]}


def q9(cursor):
    """Question 8 using the LLM fields, and the difference from Question 8."""
    original = q8(cursor)["count"]
    llm = _one(cursor, Q9_SQL)[0]
    return {"original": original, "llm": llm, "difference": llm - original}


def _rows(cursor, query):
    """Execute a query and return all result rows."""
    cursor.execute(query)
    return cursor.fetchall()


def uq1(cursor):
    """Fall 2026 acceptance rate, applicants reporting a GPA versus not."""
    return [
        {"group": g, "entries": n, "accepted": a, "pct": p}
        for g, n, a, p in _rows(cursor, UQ1_SQL)
    ]


def uq2(cursor):
    """Fall 2026 acceptance rate by degree and nationality."""
    return [
        {"degree": d, "nationality": nat, "entries": n, "accepted": a, "pct": p}
        for d, nat, n, a, p in _rows(cursor, UQ2_SQL)
    ]


# Output

def run_all(cursor):
    """Run every question and return formatted output lines."""
    r1, r2, r3, r4, r5 = q1(cursor), q2(cursor), q3(cursor), q4(cursor), q5(cursor)
    r6, r7, r9 = q6(cursor), q7(cursor), q9(cursor)

    lines = [
        f"Q1  Fall 2026 applicant count: {fmt_count(r1['count'])}",
        f"Q2  Percent international: {fmt_pct(r2['pct'])}"
        f" ({fmt_count(r2['international'])} of {fmt_count(r2['classified'])} classified entries)",
        f"Q3  Average GPA: {fmt_avg(r3['avg_gpa'])}"
        f" (n={fmt_count(r3['n_gpa'])}, {fmt_count(r3['x_gpa'])} off-scale excluded)",
        f"    Average GRE Quantitative: {fmt_avg(r3['avg_gre_q'])}"
        f" (n={fmt_count(r3['n_gre_q'])}, {fmt_count(r3['x_gre_q'])} off-scale excluded)",
        f"    Average GRE Verbal: {fmt_avg(r3['avg_gre_v'])}"
        f" (n={fmt_count(r3['n_gre_v'])}, {fmt_count(r3['x_gre_v'])} off-scale excluded)",
        f"    Average GRE Analytical Writing: {fmt_avg(r3['avg_gre_aw'])}"
        f" (n={fmt_count(r3['n_gre_aw'])}, {fmt_count(r3['x_gre_aw'])} off-scale excluded)",
        f"Q4  Average GPA of American Fall 2026 applicants: {fmt_avg(r4['avg_gpa'])}"
        f" (n={fmt_count(r4['n'])})",
        f"Q5  Fall 2025 acceptance percentage: {fmt_pct(r5['pct'])}"
        f" ({fmt_count(r5['accepted'])} of {fmt_count(r5['total'])} Fall 2025 entries)",
        f"Q6  Average GPA of accepted Fall 2026 applicants: {fmt_avg(r6['avg_gpa'])}"
        f" (n={fmt_count(r6['n'])})",
        f"Q7  JHU Masters in Computer Science count: {fmt_count(r7['count'])}",
        f"Q8  Original-field count: {fmt_count(r9['original'])}",
        f"Q9  LLM-field count: {fmt_count(r9['llm'])}",
        f"    Difference: {fmt_diff(r9['difference'])}",
        "UQ1 Fall 2026 acceptance rate by whether a GPA was reported:",
    ]
    for row in uq1(cursor):
        lines.append(
            f"    {row['group']}: {fmt_pct(row['pct'])}"
            f" ({fmt_count(row['accepted'])} of {fmt_count(row['entries'])})"
        )
    lines.append("UQ2 Fall 2026 acceptance rate by degree and nationality:")
    for row in uq2(cursor):
        lines.append(
            f"    {row['degree']}, {row['nationality']}: {fmt_pct(row['pct'])}"
            f" ({fmt_count(row['accepted'])} of {fmt_count(row['entries'])})"
        )
    return lines


def main():
    """Connect, run every question, and print the results."""
    connection = create_connection(get_db_config())
    if connection is None:
        raise SystemExit(1)
    try:
        with connection.cursor() as cursor:
            for line in run_all(cursor):
                print(line)
    finally:
        connection.close()


if __name__ == "__main__":
    main()