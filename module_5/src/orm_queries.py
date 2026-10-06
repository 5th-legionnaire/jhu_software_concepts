"""
orm_queries.py: This program repeats selected Module 3 analyses using the
SQLAlchemy ORM instead of handwritten SQL.

EN 605.256 Modern Software Concepts in Python, Module 5.
Joshua Latz (jlatz1)
Written for Module 3. Module 4 adds REQUIRED_FIELDS and fetch_one(), the
simple query function the testing assignment asks for; the Module 3 analyses
below are otherwise unchanged.

Part 6 questions, printed by main():
    Question 1, Question 4, Question 5, Question 8, Question 9, and
    User Question 2

Every query is built from the Applicant model with select(), where(),
func.count(), func.avg(), and_(), or_(), and case(), and executed through a
SQLAlchemy Session. No handwritten SQL is submitted anywhere in this module.

The remaining questions (2, 3, 6, 7, and User Question 1) are also expressed
here so the Flask page can read every result through the ORM (Part 8) instead
of duplicating database logic in its routes.

Validity ranges, matching patterns, and output formatters are imported from
query_data.py (constants and functions only; none of its SQL), so the raw SQL
and ORM answers apply identical filters and identical formatting.

Usage (from module_4/):
    python3 src/orm_queries.py          # Part 6 results
    python3 src/orm_queries.py --sql    # also print the SQL SQLAlchemy generates
"""

import sys

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.dialects import postgresql

from models import Applicant, get_session
from query_data import (
    CS_PATTERN,
    GPA_RANGE,
    GRE_AW_RANGE,
    GRE_Q_RANGE,
    GRE_V_RANGE,
    JHU_PATTERN,
    Q8_UNIVERSITY_PATTERN,
    fmt_avg,
    fmt_count,
    fmt_diff,
    fmt_pct,
)


# Reusable filter expressions (built once; no database access at import)

def _ci_eq(column, value):
    """Case-insensitive equality: LOWER(column) = 'value'."""
    return func.lower(column) == value.lower()


def _matches(column, pattern):
    """Case-insensitive regular expression match; compiles to PostgreSQL's ~*."""
    return column.regexp_match(pattern, flags="i")


def _matches_any(column, pattern):
    """or_() of one case-insensitive match per top-level alternative in pattern.

    Equivalent to matching the whole pattern at once, but reads as the list of
    alternatives it is: one condition per university name or abbreviation.
    """
    return or_(*(_matches(column, alternative) for alternative in pattern.split("|")))


# The Module 3 required schema fields, in schema order. Excludes
# program_name, university, and decision_date: those are additional columns
# outside the assignment schema (see "Additional columns" in the README).
REQUIRED_FIELDS = (
    "p_id", "program", "comments", "date_added", "url", "status", "term",
    "us_or_international", "gpa", "gre", "gre_v", "gre_aw", "degree",
    "llm_generated_program", "llm_generated_university",
)

FALL_2026 = _ci_eq(Applicant.term, "fall 2026")
FALL_2025 = _ci_eq(Applicant.term, "fall 2025")
ACCEPTED = _ci_eq(Applicant.status, "accepted")
AMERICAN = _ci_eq(Applicant.us_or_international, "american")
INTERNATIONAL = _ci_eq(Applicant.us_or_international, "international")
PHD = _ci_eq(Applicant.degree, "phd")
MASTERS = _ci_eq(Applicant.degree, "masters")
VALID_GPA = Applicant.gpa.between(*GPA_RANGE)


def _pct(numerator, denominator):
    """100.0 * numerator / NULLIF(denominator, 0), computed in the database."""
    return 100.0 * numerator / func.nullif(denominator, 0)


# Statements: each returns a select() built from the Applicant model

def q1_stmt():
    """Fall 2026 applicant count."""
    return select(func.count()).select_from(Applicant).where(FALL_2026)


def q2_stmt():
    """Percentage international among entries with a nationality classification."""
    international = func.count().filter(INTERNATIONAL)
    classified = func.count()
    return (
        select(international, classified, _pct(international, classified))
        .select_from(Applicant)
        .where(and_(Applicant.us_or_international.is_not(None),
                    func.trim(Applicant.us_or_international) != ""))
    )


def q3_stmt():
    """Average of each metric over applicants providing it, within its valid range."""
    metrics = [
        (Applicant.gpa, GPA_RANGE),
        (Applicant.gre, GRE_Q_RANGE),
        (Applicant.gre_v, GRE_V_RANGE),
        (Applicant.gre_aw, GRE_AW_RANGE),
    ]
    averages = [func.avg(col).filter(col.between(*rng)) for col, rng in metrics]
    included = [func.count(col).filter(col.between(*rng)) for col, rng in metrics]
    excluded = [func.count(col) - func.count(col).filter(col.between(*rng)) for col, rng in metrics]
    return select(*averages, *included, *excluded).select_from(Applicant)


def q4_stmt():
    """Average GPA of American Fall 2026 applicants."""
    return select(func.avg(Applicant.gpa), func.count(Applicant.gpa)).where(
        and_(FALL_2026, AMERICAN, VALID_GPA))


def q5_stmt():
    """Fall 2025 acceptance percentage over all Fall 2025 entries."""
    accepted = func.count().filter(ACCEPTED)
    total = func.count()
    return select(accepted, total, _pct(accepted, total)).select_from(Applicant).where(FALL_2025)


def q6_stmt():
    """Average GPA of accepted Fall 2026 applicants."""
    return select(func.avg(Applicant.gpa), func.count(Applicant.gpa)).where(
        and_(FALL_2026, ACCEPTED, VALID_GPA))


def q7_stmt():
    """JHU Masters in Computer Science entries, original fields."""
    return select(func.count()).select_from(Applicant).where(and_(
        _matches(Applicant.program, JHU_PATTERN),
        _matches(Applicant.program, CS_PATTERN),
        MASTERS))


def q8_stmt():
    """Fall 2026 CS PhD acceptances at the four universities, original fields."""
    return select(func.count()).select_from(Applicant).where(and_(
        FALL_2026, ACCEPTED, PHD,
        _matches(Applicant.program, CS_PATTERN),
        _matches_any(Applicant.program, Q8_UNIVERSITY_PATTERN)))


def q9_stmt():
    """Question 8 with university and program identified from the LLM fields."""
    return select(func.count()).select_from(Applicant).where(and_(
        FALL_2026, ACCEPTED, PHD,
        _matches(Applicant.llm_generated_program, CS_PATTERN),
        _matches_any(Applicant.llm_generated_university, Q8_UNIVERSITY_PATTERN)))


def uq1_stmt():
    """Fall 2026 acceptance rate by whether a usable GPA was reported."""
    group = case((VALID_GPA, "Reported GPA"), else_="No usable GPA").label("gpa_reported")
    accepted = func.count().filter(ACCEPTED)
    total = func.count()
    return (
        select(group, total, accepted, _pct(accepted, total))
        .select_from(Applicant)
        .where(FALL_2026)
        .group_by(group)
        .order_by(group.desc())
    )


def uq2_stmt():
    """Fall 2026 acceptance rate by degree (PhD, Masters) and nationality."""
    degree = case((PHD, "PhD"), else_="Masters").label("degree_group")
    nationality = case((AMERICAN, "American"), else_="International").label("nationality")
    accepted = func.count().filter(ACCEPTED)
    total = func.count()
    return (
        select(degree, nationality, total, accepted, _pct(accepted, total))
        .select_from(Applicant)
        .where(and_(FALL_2026, or_(PHD, MASTERS), or_(AMERICAN, INTERNATIONAL)))
        .group_by(degree, nationality)
        .order_by(degree.desc(), nationality)
    )


# Runners: execute a statement in a Session and return plain Python values.
# Return shapes match query_data.py's, so the two can be compared directly.

def q1(session):
    """Fall 2026 applicant count."""
    return {"count": session.scalar(q1_stmt())}


def q2(session):
    """Percentage international among entries with a nationality classification."""
    international, classified, pct = session.execute(q2_stmt()).one()
    return {"international": international, "classified": classified, "pct": pct}


def q3(session):
    """Average GPA and GRE scores, each over applicants providing that metric."""
    keys = ("avg_gpa", "avg_gre_q", "avg_gre_v", "avg_gre_aw",
            "n_gpa", "n_gre_q", "n_gre_v", "n_gre_aw",
            "x_gpa", "x_gre_q", "x_gre_v", "x_gre_aw")
    return dict(zip(keys, session.execute(q3_stmt()).one()))


def q4(session):
    """Average GPA of American Fall 2026 applicants."""
    avg, n = session.execute(q4_stmt()).one()
    return {"avg_gpa": avg, "n": n}


def q5(session):
    """Fall 2025 acceptance percentage."""
    accepted, total, pct = session.execute(q5_stmt()).one()
    return {"accepted": accepted, "total": total, "pct": pct}


def q6(session):
    """Average GPA of accepted Fall 2026 applicants."""
    avg, n = session.execute(q6_stmt()).one()
    return {"avg_gpa": avg, "n": n}


def q7(session):
    """JHU Masters in Computer Science entries, original fields."""
    return {"count": session.scalar(q7_stmt())}


def q8(session):
    """Fall 2026 CS PhD acceptances at the four universities, original fields."""
    return {"count": session.scalar(q8_stmt())}


def q9(session):
    """Question 8 using the LLM fields, and the difference from Question 8."""
    original = q8(session)["count"]
    llm = session.scalar(q9_stmt())
    return {"original": original, "llm": llm, "difference": llm - original}


def uq1(session):
    """Fall 2026 acceptance rate, applicants reporting a GPA versus not."""
    return [{"group": g, "entries": n, "accepted": a, "pct": p}
            for g, n, a, p in session.execute(uq1_stmt())]


def uq2(session):
    """Fall 2026 acceptance rate by degree and nationality."""
    return [{"degree": d, "nationality": nat, "entries": n, "accepted": a, "pct": p}
            for d, nat, n, a, p in session.execute(uq2_stmt())]


def applicant_dict(applicant):
    """One Applicant row as a dict of the Module 3 required schema fields."""
    return {field: getattr(applicant, field) for field in REQUIRED_FIELDS}


def fetch_one(session):
    """Return one applicant row as a dict with the Module 3 required schema keys.

    This is the simple query function the assignment's database-writes
    section asks for: proof that a row can be read back with the right
    shape, independent of any analysis. Returns None if the table is empty.
    """
    applicant = session.scalars(select(Applicant).order_by(Applicant.p_id).limit(1)).first()
    return applicant_dict(applicant) if applicant else None


def dataset_summary(session):
    """Total entries and the range of date_added, for the page header."""
    total, first, last = session.execute(
        select(func.count(), func.min(Applicant.date_added), func.max(Applicant.date_added))
        .select_from(Applicant)).one()
    return {"total": total, "first_added": first, "last_added": last}


def all_results(session):
    """Every question's result, for the Flask analysis page."""
    return {name: fn(session) for name, fn in (
        ("q1", q1), ("q2", q2), ("q3", q3), ("q4", q4), ("q5", q5), ("q6", q6),
        ("q7", q7), ("q9", q9), ("uq1", uq1), ("uq2", uq2))}


# Output

def _sql(stmt):
    """The PostgreSQL SQL SQLAlchemy generates for a statement, with its bound parameters.

    Parameters are shown separately rather than inlined: SQLAlchemy's
    literal-value rendering double-escapes backslashes, which would display
    the regex word anchors incorrectly even though execution is unaffected.
    """
    compiled = stmt.compile(dialect=postgresql.dialect())
    return f"{compiled}\nparameters: {compiled.params}"


PART_6 = [  # (label, statement builders) for --sql output
    ("Q1", [q1_stmt]), ("Q4", [q4_stmt]), ("Q5", [q5_stmt]),
    ("Q8", [q8_stmt]), ("Q9", [q9_stmt]), ("UQ2", [uq2_stmt]),
]


def part6_lines(session):
    """Formatted output for the Part 6 questions."""
    r1, r4, r5, r9 = q1(session), q4(session), q5(session), q9(session)
    lines = [
        f"Q1  Fall 2026 applicant count: {fmt_count(r1['count'])}",
        f"Q4  Average GPA of American Fall 2026 applicants: {fmt_avg(r4['avg_gpa'])}"
        f" (n={fmt_count(r4['n'])})",
        f"Q5  Fall 2025 acceptance percentage: {fmt_pct(r5['pct'])}"
        f" ({fmt_count(r5['accepted'])} of {fmt_count(r5['total'])} Fall 2025 entries)",
        f"Q8  Original-field count: {fmt_count(r9['original'])}",
        f"Q9  LLM-field count: {fmt_count(r9['llm'])}",
        f"    Difference: {fmt_diff(r9['difference'])}",
        "UQ2 Fall 2026 acceptance rate by degree and nationality:",
    ]
    for row in uq2(session):
        lines.append(
            f"    {row['degree']}, {row['nationality']}: {fmt_pct(row['pct'])}"
            f" ({fmt_count(row['accepted'])} of {fmt_count(row['entries'])})"
        )
    return lines


def main():
    """Run the Part 6 questions through the ORM and print the results."""
    show_sql = "--sql" in sys.argv[1:]
    print("SQLAlchemy ORM results")
    with get_session() as session:
        for line in part6_lines(session):
            print(line)
    if show_sql:
        for label, builders in PART_6:
            for build in builders:
                print(f"\n-- {label}\n{_sql(build())}")


if __name__ == "__main__":  # pragma: no cover - command line entry point
    main()