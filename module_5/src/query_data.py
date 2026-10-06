"""
query_data.py: This program answers the Module 3 analysis questions about
Grad Cafe submissions using SQL queries executed through psycopg.

EN 605.256 Modern Software Concepts in Python, Module 5.
Joshua Latz (jlatz1)
Written for Module 3. Module 5 replaced the SQL text constants with composed
builders (CHG-05 in CHANGES.md); the questions, their ranges, and their answers
are unchanged, which tests/snapshots/m4_run_all.txt proves.

Contains:
    Validity ranges:  GPA_RANGE, GRE_Q_RANGE, GRE_V_RANGE, GRE_AW_RANGE
    Formatters:       fmt_count(), fmt_pct(), fmt_avg(), fmt_diff()
    Builders:         build_q1() to build_q9(), build_uq1(), build_uq2(), QUESTIONS
    Executor:         _execute(), the only place a statement reaches the cursor
    Questions:        q1() to q9(), uq1(), uq2()
    Output:           run_all(), main()

Every analysis is expressed in SQL. A builder composes a statement with
psycopg's sql module and returns it with its parameters, touching no database;
the executor runs it. Every value, constants included, travels as a bound
parameter, and every statement ends in a LIMIT from db_safety.clamp_limit().
The only literals left in the SQL text are the formula's own numbers
(100.0 for a percentage, 0 in NULLIF). The text that runs can be rendered
without a connection: ``stmt.as_string(None)``.

Usage (from module_5/):
    python3 src/query_data.py
"""

from psycopg import sql

from db_safety import MAX_LIMIT, clamp_limit
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


# SQL builders
#
# Each build_* function returns (statement, params). A statement is a
# psycopg sql.Composed: identifiers go through sql.Identifier, values through
# sql.Placeholder, and the static text is a sql.SQL literal. .format() on a
# sql.SQL is psycopg's composition API and quotes what it inserts; it is not
# string formatting.

APPLICANTS = sql.Identifier("applicants")

# The formula's own numbers, not data: a percentage is 100.0 * part / total,
# and NULLIF turns a zero total into NULL rather than a division error.
PERCENT = "100.0 * {part} / NULLIF(COUNT(*), 0)"


def _col(name):
    return sql.Identifier(name)


def _ph(name):
    return sql.Placeholder(name)


def _lower_eq(column, key):
    """LOWER(column) = %(key)s, for a value the caller supplies already lowercased."""
    return sql.SQL("LOWER({column}) = {value}").format(column=_col(column), value=_ph(key))


def _between(column, key):
    """column BETWEEN %(key_lo)s AND %(key_hi)s."""
    return sql.SQL("{column} BETWEEN {low} AND {high}").format(
        column=_col(column), low=_ph(f"{key}_lo"), high=_ph(f"{key}_hi"))


def _bounds(key, bounds):
    """The two parameters _between() names, from a (low, high) range."""
    return {f"{key}_lo": bounds[0], f"{key}_hi": bounds[1]}


def _text(key):
    """A text-typed parameter, so PostgreSQL need not infer the type of a bare label."""
    return sql.SQL("CAST({value} AS TEXT)").format(value=_ph(key))


def _percent(part):
    """A percentage of COUNT(*), given the counted part."""
    return sql.SQL(PERCENT).format(part=part)


def _finish(statement, params, rows):
    """Append the LIMIT and its parameter.

    Aggregates are limited on output rows, not on rows evaluated: LIMIT caps
    what comes back, so the analysis answers do not change. ``rows`` is 1 for a
    single-row aggregate and MAX_LIMIT for a grouped result.
    """
    limited = statement + sql.SQL(" LIMIT ") + _ph("limit")
    return limited, {**params, "limit": clamp_limit(rows)}


FALL_2026 = {"term": "fall 2026"}
FALL_2025 = {"term": "fall 2025"}
ACCEPTED = {"status": "accepted"}


def build_q1():
    """Fall 2026 applicant count."""
    statement = sql.SQL("SELECT COUNT(*) FROM {table} WHERE {term}").format(
        table=APPLICANTS, term=_lower_eq("term", "term"))
    return _finish(statement, FALL_2026, 1)


def build_q2():
    """Percentage international among entries with a nationality classification."""
    international = sql.SQL("COUNT(*) FILTER (WHERE {nationality})").format(
        nationality=_lower_eq("us_or_international", "international"))
    statement = sql.SQL(
        "SELECT {international} AS international, COUNT(*) AS classified, "
        "{pct} AS pct_international FROM {table} "
        "WHERE {nationality} IS NOT NULL AND TRIM({nationality}) <> {blank}"
    ).format(international=international, pct=_percent(international), table=APPLICANTS,
             nationality=_col("us_or_international"), blank=_ph("blank"))
    return _finish(statement, {"international": "international", "blank": ""}, 1)


def build_q3():
    """Average GPA and GRE scores, each over applicants providing that metric."""
    metrics = (("gpa", "gpa", GPA_RANGE), ("gre", "gre_q", GRE_Q_RANGE),
               ("gre_v", "gre_v", GRE_V_RANGE), ("gre_aw", "gre_aw", GRE_AW_RANGE))
    averages, counts, excluded, params = [], [], [], {}
    for column, key, bounds in metrics:
        within = _between(column, key)
        averages.append(sql.SQL("AVG({c}) FILTER (WHERE {w}) AS {a}").format(
            c=_col(column), w=within, a=_col(f"avg_{key}")))
        counts.append(sql.SQL("COUNT({c}) FILTER (WHERE {w}) AS {a}").format(
            c=_col(column), w=within, a=_col(f"n_{key}")))
        excluded.append(sql.SQL("COUNT({c}) - COUNT({c}) FILTER (WHERE {w}) AS {a}").format(
            c=_col(column), w=within, a=_col(f"x_{key}")))
        params.update(_bounds(key, bounds))
    statement = sql.SQL("SELECT {columns} FROM {table}").format(
        columns=sql.SQL(", ").join(averages + counts + excluded), table=APPLICANTS)
    return _finish(statement, params, 1)


def build_q4():
    """Average GPA of American Fall 2026 applicants."""
    statement = sql.SQL(
        "SELECT AVG({gpa}), COUNT({gpa}) FROM {table} WHERE {term} AND {nationality} AND {valid}"
    ).format(gpa=_col("gpa"), table=APPLICANTS, term=_lower_eq("term", "term"),
             nationality=_lower_eq("us_or_international", "american"),
             valid=_between("gpa", "gpa"))
    return _finish(statement, {**FALL_2026, "american": "american", **_bounds("gpa", GPA_RANGE)}, 1)


def build_q5():
    """Fall 2025 acceptance percentage over all Fall 2025 entries."""
    accepted = sql.SQL("COUNT(*) FILTER (WHERE {status})").format(
        status=_lower_eq("status", "status"))
    statement = sql.SQL(
        "SELECT {accepted} AS accepted, COUNT(*) AS total, {pct} AS pct_accepted "
        "FROM {table} WHERE {term}"
    ).format(accepted=accepted, pct=_percent(accepted), table=APPLICANTS,
             term=_lower_eq("term", "term"))
    return _finish(statement, {**FALL_2025, **ACCEPTED}, 1)


def build_q6():
    """Average GPA of accepted Fall 2026 applicants."""
    statement = sql.SQL(
        "SELECT AVG({gpa}), COUNT({gpa}) FROM {table} WHERE {term} AND {status} AND {valid}"
    ).format(gpa=_col("gpa"), table=APPLICANTS, term=_lower_eq("term", "term"),
             status=_lower_eq("status", "status"), valid=_between("gpa", "gpa"))
    return _finish(statement, {**FALL_2026, **ACCEPTED, **_bounds("gpa", GPA_RANGE)}, 1)


def build_q7():
    """JHU Masters in Computer Science entries, original fields.

    ``program`` holds "Program, University" as the site presents it, so both
    the university and the program are matched within it.
    """
    statement = sql.SQL(
        "SELECT COUNT(*) FROM {table} WHERE {program} ~* {jhu} AND {program} ~* {cs} AND {degree}"
    ).format(table=APPLICANTS, program=_col("program"), jhu=_ph("jhu"), cs=_ph("cs"),
             degree=_lower_eq("degree", "masters"))
    return _finish(statement, {"jhu": JHU_PATTERN, "cs": CS_PATTERN, "masters": "masters"}, 1)


def _q8_family(program_column, university_column):
    """Fall 2026 accepted CS PhD entries at the four universities, for one field pair."""
    statement = sql.SQL(
        "SELECT COUNT(*) FROM {table} WHERE {term} AND {status} AND {degree} "
        "AND {program} ~* {cs} AND {university} ~* {universities}"
    ).format(table=APPLICANTS, term=_lower_eq("term", "term"),
             status=_lower_eq("status", "status"), degree=_lower_eq("degree", "phd"),
             program=_col(program_column), university=_col(university_column),
             cs=_ph("cs"), universities=_ph("universities"))
    params = {**FALL_2026, **ACCEPTED, "phd": "phd", "cs": CS_PATTERN,
              "universities": Q8_UNIVERSITY_PATTERN}
    return _finish(statement, params, 1)


def build_q8():
    """Fall 2026 CS PhD acceptances at the four universities, original fields."""
    return _q8_family("program", "program")


def build_q9():
    """Question 8 with university and program identified from the LLM fields.

    Term, degree, and status stay on the original fields.
    """
    return _q8_family("llm_generated_program", "llm_generated_university")


def build_uq1():
    """User question 1: Fall 2026 acceptance rate, GPA reported versus not.

    Do applicants who report a GPA post acceptances at a different rate from
    those who do not? A direct measure of whether self-reporting correlates
    with outcome (see limitations.pdf).
    """
    accepted = sql.SQL("COUNT(*) FILTER (WHERE {status})").format(
        status=_lower_eq("status", "status"))
    group = sql.SQL("CASE WHEN {valid} THEN {reported} ELSE {unreported} END").format(
        valid=_between("gpa", "gpa"), reported=_text("reported"), unreported=_text("unreported"))
    statement = sql.SQL(
        "SELECT {group} AS gpa_reported, COUNT(*) AS entries, {accepted} AS accepted, "
        "{pct} AS pct_accepted FROM {table} WHERE {term} GROUP BY 1 ORDER BY 1 DESC"
    ).format(group=group, accepted=accepted, pct=_percent(accepted), table=APPLICANTS,
             term=_lower_eq("term", "term"))
    params = {**FALL_2026, **ACCEPTED, **_bounds("gpa", GPA_RANGE),
              "reported": "Reported GPA", "unreported": "No usable GPA"}
    return _finish(statement, params, MAX_LIMIT)


def build_uq2():
    """User question 2: Fall 2026 acceptance rate by degree and nationality.

    How do acceptance rates differ between American and International
    applicants, for PhD and Masters programs?
    """
    accepted = sql.SQL("COUNT(*) FILTER (WHERE {status})").format(
        status=_lower_eq("status", "status"))
    degree = sql.SQL("CASE LOWER({degree}) WHEN {phd} THEN {phd_label} ELSE {masters_label} END"
                     ).format(degree=_col("degree"), phd=_ph("phd"), phd_label=_text("phd_label"),
                              masters_label=_text("masters_label"))
    nationality = sql.SQL(
        "CASE LOWER({nat}) WHEN {american} THEN {american_label} ELSE {international_label} END"
    ).format(nat=_col("us_or_international"), american=_ph("american"),
             american_label=_text("american_label"),
             international_label=_text("international_label"))
    statement = sql.SQL(
        "SELECT {degree} AS degree_group, {nationality} AS nationality, COUNT(*) AS entries, "
        "{accepted} AS accepted, {pct} AS pct_accepted FROM {table} "
        "WHERE {term} AND LOWER({raw_degree}) IN ({phd}, {masters}) "
        "AND LOWER({raw_nat}) IN ({american}, {international}) "
        "GROUP BY 1, 2 ORDER BY 1 DESC, 2"
    ).format(degree=degree, nationality=nationality, accepted=accepted, pct=_percent(accepted),
             table=APPLICANTS, term=_lower_eq("term", "term"), raw_degree=_col("degree"),
             raw_nat=_col("us_or_international"), phd=_ph("phd"), masters=_ph("masters"),
             american=_ph("american"), international=_ph("international"))
    params = {**FALL_2026, **ACCEPTED, "phd": "phd", "masters": "masters",
              "american": "american", "international": "international",
              "phd_label": "PhD", "masters_label": "Masters",
              "american_label": "American", "international_label": "International"}
    return _finish(statement, params, MAX_LIMIT)


# Every statement the analysis runs, by question name. The SQL guard tests
# iterate this mapping, so a new question cannot skip the LIMIT check.
QUESTIONS = {
    "q1": build_q1, "q2": build_q2, "q3": build_q3, "q4": build_q4, "q5": build_q5,
    "q6": build_q6, "q7": build_q7, "q8": build_q8, "q9": build_q9,
    "uq1": build_uq1, "uq2": build_uq2,
}


# Execution

def _execute(cursor, statement, params):
    """Run one composed statement. The only call to cursor.execute in this module."""
    cursor.execute(statement, params)


def _one(cursor, build):
    """Build and execute a statement, and return its single result row."""
    statement, params = build()
    _execute(cursor, statement, params)
    return cursor.fetchone()


def _rows(cursor, build):
    """Build and execute a statement, and return all of its result rows."""
    statement, params = build()
    _execute(cursor, statement, params)
    return cursor.fetchall()


# Question functions: each runs its SQL and returns plain Python values

def q1(cursor):
    """Fall 2026 applicant count."""
    return {"count": _one(cursor, build_q1)[0]}


def q2(cursor):
    """Percentage international among entries with a nationality classification."""
    international, classified, pct = _one(cursor, build_q2)
    return {"international": international, "classified": classified, "pct": pct}


def q3(cursor):
    """Average GPA and GRE scores, each over applicants providing that metric."""
    row = _one(cursor, build_q3)
    keys = ("avg_gpa", "avg_gre_q", "avg_gre_v", "avg_gre_aw",
            "n_gpa", "n_gre_q", "n_gre_v", "n_gre_aw",
            "x_gpa", "x_gre_q", "x_gre_v", "x_gre_aw")
    return dict(zip(keys, row))


def q4(cursor):
    """Average GPA of American Fall 2026 applicants."""
    avg, n = _one(cursor, build_q4)
    return {"avg_gpa": avg, "n": n}


def q5(cursor):
    """Fall 2025 acceptance percentage."""
    accepted, total, pct = _one(cursor, build_q5)
    return {"accepted": accepted, "total": total, "pct": pct}


def q6(cursor):
    """Average GPA of accepted Fall 2026 applicants."""
    avg, n = _one(cursor, build_q6)
    return {"avg_gpa": avg, "n": n}


def q7(cursor):
    """JHU Masters in Computer Science entries, original fields."""
    return {"count": _one(cursor, build_q7)[0]}


def q8(cursor):
    """Fall 2026 CS PhD acceptances at the four universities, original fields."""
    return {"count": _one(cursor, build_q8)[0]}


def q9(cursor):
    """Question 8 using the LLM fields, and the difference from Question 8."""
    original = q8(cursor)["count"]
    llm = _one(cursor, build_q9)[0]
    return {"original": original, "llm": llm, "difference": llm - original}


def uq1(cursor):
    """Fall 2026 acceptance rate, applicants reporting a GPA versus not."""
    return [
        {"group": g, "entries": n, "accepted": a, "pct": p}
        for g, n, a, p in _rows(cursor, build_uq1)
    ]


def uq2(cursor):
    """Fall 2026 acceptance rate by degree and nationality."""
    return [
        {"degree": d, "nationality": nat, "entries": n, "accepted": a, "pct": p}
        for d, nat, n, a, p in _rows(cursor, build_uq2)
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


if __name__ == "__main__":  # pragma: no cover - command line entry point
    main()