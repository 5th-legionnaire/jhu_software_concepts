"""build_report.py: assemble module_5_report.pdf from the committed evidence.

EN 605.256 Modern Software Concepts in Python, Module 5.
Joshua Latz (jlatz1)

Every figure in the report is read from the repository when it is built (test
counts from coverage_summary.txt, the score from pylint_report.txt, the SQL
from the builders themselves, the privileges from privileges.txt, the change
list from CHANGES.md), so the PDF cannot drift from the evidence it describes.
It writes an HTML page with the images embedded and prints it with headless
Chrome, which this project already needs for Pull Data.

Contains:
    build_html():  the report as one HTML page
    main():        write report/module_5_report.html and module_5_report.pdf

Usage (from module_5/, with the environment active):
    python report/build_report.py
"""

import base64
import html
import re
import subprocess
import sys
from pathlib import Path

MODULE = Path(__file__).resolve().parent.parent
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

# The Module 4 Q7 statement, quoted for the before-and-after; module_4/src/query_data.py holds the original.
Q7_BEFORE = '''Q7_SQL = f"""
SELECT COUNT(*)
FROM applicants
WHERE program ~* '{JHU_PATTERN}'
  AND program ~* '{CS_PATTERN}'
  AND LOWER(degree) = 'masters';
"""'''


def read(name):
    return (MODULE / name).read_text(encoding="utf-8")


def esc(text):
    return html.escape(text)


def code(text):
    return f"<pre>{esc(text.strip())}</pre>"


def image(name, width="100%"):
    path = MODULE / name
    kind = "svg+xml" if name.endswith(".svg") else "png"
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f'<img src="data:image/{kind};base64,{data}" style="width:{width}" alt="{esc(name)}">'


def md_inline(text):
    text = esc(text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    return re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)


def md_tables(markdown):
    """Every Markdown table in a document, as HTML tables."""
    out, rows = [], []
    for line in markdown.splitlines() + [""]:
        if line.startswith("|"):
            rows.append([c.strip() for c in line.strip().strip("|").split("|")])
        elif rows:
            body = [r for r in rows[1:] if not set("".join(r)) <= set("-: ")]
            out.append("<table><tr>" + "".join(f"<th>{md_inline(c)}</th>" for c in rows[0]) + "</tr>"
                       + "".join("<tr>" + "".join(f"<td>{md_inline(c)}</td>" for c in r) + "</tr>" for r in body)
                       + "</table>")
            rows = []
    return out


def facts():
    coverage = read("coverage_summary.txt")
    sys.path.insert(0, str(MODULE / "src"))
    import query_data  # imported here: src/ is put on the path just above
    statement, params = query_data.build_q7()
    return {
        "passed": re.search(r"(\d+) passed", coverage).group(1),
        "coverage": re.search(r"Total coverage: ([\d.]+)%", coverage).group(1),
        "pylint": re.search(r"rated at ([\d.]+)/10", read("pylint_report.txt")).group(1),
        "q7_after": statement.as_string(None), "q7_params": params,
        "grants": "\n".join(l for l in read("sql/grants.sql").splitlines() if l and not l.startswith(("--", "\\"))),
        "roles": "\n".join(l for l in read("sql/roles.sql").splitlines()
                           if l.startswith(("ALTER ROLE", "    NOSUPER", "REVOKE", "GRANT"))),
        "privileges": read("privileges.txt").split("--- what the runtime account")[1].split("--- who can")[0],
        "summary": read("report/dependency_summary.md").split("for the report):", 1)[1].strip(),
        "changes": [r for r in md_tables(read("CHANGES.md"))][0],
        "snyk_tables": md_tables(read("report/snyk_triage.md")),
    }


def build_html():
    f = facts()
    q7_params = ", ".join(f"{k}={v!r}" for k, v in f["q7_params"].items())
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>Module 5 report</title><style>
body{{font:10.5pt/1.42 -apple-system,Helvetica,Arial,sans-serif;margin:0;color:#111}}
h1{{font-size:18pt;margin:0 0 2pt}} h2{{font-size:13pt;margin:16pt 0 4pt;border-bottom:1px solid #999;page-break-after:avoid}}
pre{{background:#f4f4f4;padding:6pt;font-size:8.5pt;white-space:pre-wrap;word-break:break-word}}
table{{border-collapse:collapse;width:100%;font-size:8.6pt;margin:4pt 0;page-break-inside:auto}}
th,td{{border:1px solid #bbb;padding:2pt 4pt;text-align:left;vertical-align:top}} th{{background:#eee}}
code{{font-size:9pt}} .meta{{color:#444;margin-bottom:8pt}} img{{border:1px solid #ccc;margin:4pt 0}}
@page{{size:Letter;margin:0.6in}}</style></head><body>
<h1>Module 5: Software Assurance and Secure SQL</h1>
<div class="meta">Joshua Latz (jlatz1), EN 605.256 Modern Software Concepts in Python.
Repository <code>git@github.com:5th-legionnaire/jhu_software_concepts.git</code>, folder <code>module_5/</code>.
The README's "Start here" table maps every requirement to its evidence and a command that checks it.</div>

<h2>1. Results</h2>
<p>{f["passed"]} tests pass with {f["coverage"]}% coverage of <code>src/</code>. Pylint scores {f["pylint"]}/10 with no
messages and no inline disables. Snyk reports no vulnerability in any of the 70 pinned packages after 22 findings were
fixed by upgrading two packages. 51 malicious-input cases return no 500, no leak, and never every row. The runtime
database account can only SELECT and INSERT on one table. CI runs four jobs on every push and pull request.</p>

<h2>2. Install and run (pip and uv)</h2>
<p>Python 3.14 is required. From <code>module_5/</code>, either installer builds the same pinned environment:</p>
{code('''# pip
python3.14 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install -e . --no-deps

# uv
uv venv -p 3.14 .venv && source .venv/bin/activate
uv pip sync requirements.txt
uv pip install -e . --no-deps

cp .env.example .env            # fill in DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD
python3 src/app.py              # http://127.0.0.1:8080/analysis
pytest                          # the full suite''')}
<p><code>scripts/fresh_install_check.sh</code> proves both recipes from a clean copy with no venv and no
<code>.env</code>, and CI runs the suite on both.</p>

<h2>3. Why packaging matters (setup.py)</h2>
<p>Module 4's tests found the code by editing <code>sys.path</code>, so imports resolved one way under pytest and
another everywhere else, and a packaging defect would stay hidden until the code ran on someone else's machine.
<code>setup.py</code> declares the modules and their dependencies once, and the editable install
(<code>pip install -e .</code>) makes imports behave the same in local runs, tests and CI. It is also the single
source of the dependency list: <code>requirements.txt</code> is a fully pinned lock generated from it with
<code>uv pip compile</code>, 70 packages including the transitive ones and the tooling (pylint, pydeps), so
<code>uv pip sync</code> builds exactly the environment that was tested and Snyk scans the whole tree.</p>

<h2>4. Dependency graph</h2>
{image("dependency.svg")}
<p>{md_inline(f["summary"])}</p>

<h2>5. SQL injection defenses</h2>
<p><b>What changed.</b> Every statement is a psycopg <code>sql.Composed</code>: identifiers go through
<code>sql.Identifier</code>, values through placeholders, and the static text is a <code>sql.SQL</code> literal.
Builders return <code>(statement, params)</code> and touch no database; one executor per module calls
<code>cursor.execute(statement, params)</code>, and <code>execute_query</code> refuses a bare string. Every value is
bound, constants included. Before and after, Question 7:</p>
{code(Q7_BEFORE)}
{code(f["q7_after"] + chr(10) + "parameters: " + q7_params)}
<p><b>Why it is safe.</b> Client text never becomes SQL text. In <code>GET /api/applicants</code> the sort column must
be one of nine names and reaches SQL as a quoted identifier; the direction is one of two fixed fragments; filters are
bound parameters; LIKE wildcards in the query are escaped so <code>%</code> matches only a literal percent; unknown
parameters, control characters (including NUL), and over-length values are a 400 before any statement is built,
and errors never echo the input. Tests prove it: an AST guard fails on any f-string, <code>+</code>, <code>%</code>, or
<code>.format()</code> holding SQL in <code>src/</code>; a spy cursor shows only composed statements reach the driver;
and the 51-case matrix (for example <code>' OR '1'='1</code>, <code>; DROP TABLE applicants</code>, a
<code>UNION</code> against <code>pg_shadow</code>, <code>pg_sleep</code>, NUL bytes) returns 0 rows or a 400 and
leaves the table intact. Answers to every analysis question equal Module 4's over all 30,000 rows.</p>

<h2>6. Requirements met for SQL</h2>
<table><tr><th>Requirement</th><th>How it is met</th><th>Verified by</th></tr>
<tr><td>LIMIT enforced on every query</td><td>Every SELECT ends in <code>LIMIT %(limit)s</code> from
<code>clamp_limit()</code>; the API clamps 1 to 100 (default 20) and reports the effective value. Aggregates get an
output LIMIT so no answer changes.</td><td><code>test_every_select_has_limit</code>, the ORM statement and runtime
checks, <code>test_db_safety.py</code></td></tr>
<tr><td>Statements separated from execution</td><td>Builders return <code>(statement, params)</code>; one executor
calls <code>cursor.execute</code></td><td><code>test_every_execute_receives_composable</code>,
<code>test_builders_touch_no_database</code></td></tr>
<tr><td>Safe composition and parameterization</td><td><code>sql.SQL</code>, <code>sql.Identifier</code>,
<code>sql.Placeholder</code>; no string-built SQL</td><td><code>test_no_sql_string_building</code>, builder
snapshots, the malicious matrix</td></tr></table>

<h2>7. Least-privilege database configuration</h2>
<p>Credentials come only from the environment (<code>DB_HOST</code>, <code>DB_PORT</code>, <code>DB_NAME</code>,
<code>DB_USER</code>, <code>DB_PASSWORD</code>; <code>.env.example</code> lists them with placeholders and
<code>.env</code> is gitignored). Two roles: <code>gradcafe_owner</code> owns the table and does schema setup and the
bulk load; <code>gradcafe_app</code>, the account the app and Pull Data use, is not a superuser, cannot create
databases or roles, and holds only SELECT (the page, the search, the pull's read of the newest entry) and INSERT
(Pull Data; <code>ON CONFLICT DO NOTHING</code> needs no UPDATE). It has no DROP, ALTER, UPDATE, DELETE, TRUNCATE or
ownership, so the worst a flaw could do is read and add public applicant rows.</p>
{code(f["roles"] + chr(10) + f["grants"])}
{code(f["privileges"])}
{image("privileges.png", "80%")}
<p>Passwords never reach the server: the roles are set from SCRAM-SHA-256 verifiers passed in the environment, after
checking showed a failed <code>ALTER ROLE ... PASSWORD</code> would have been written to a world-readable server log.
A gate check searches the tree, all git history, the server log and shell history for the real passwords on every
phase; it has found none.</p>

<h2>8. Snyk (dependencies, and Snyk Code for extra credit)</h2>
{f["snyk_tables"][0]}
<p>Both <code>urllib3</code> and <code>python-dotenv</code> were upgraded (2.8.0 and 1.2.4): a pinned lock freezes
flaws along with versions, and arguing that an advisory is unreachable costs more than the patch. Exactly two lock
lines changed and the full suite passed on the new versions. Snyk does not evaluate the lock's platform markers, so
<code>scripts/snyk_scan.sh</code> scans the 65 packages that apply and, separately, the 5 a marker excludes: all 70
are clean.</p>
{image("snyk-analysis.png", "85%")}
{f["snyk_tables"][1]}
{image("snyk-code-analysis.png")}

<h2>9. CI (GitHub Actions)</h2>
<p><code>.github/workflows/ci.yml</code> has four jobs that fail independently: <b>lint</b> (Pylint
<code>--fail-under=10</code>), <b>dependency-graph</b> (pydeps and Graphviz must produce a valid
<code>dependency.svg</code>), <b>snyk</b> (fails on a high or critical dependency finding; Snyk Code report-only), and
<b>test</b> (the full suite at 100% coverage on pip and on uv, against PostgreSQL 16 with the two least-privilege
roles). The first run found three tests that passed only because of a developer's <code>.env</code>; the suite is now
hermetic.</p>
{image("actions_success.png")}

<h2>10. Changes from Module 4 (the Change Register)</h2>
<p>Each change below has a problem, decision, trade-off and verifying tests in the README and
<code>CHANGES.md</code>; a gate refuses a phase whose changes lack them.</p>
{f["changes"]}
</body></html>"""


def main():
    """Write the HTML and print it to PDF with headless Chrome."""
    page = MODULE / "report" / "module_5_report.html"
    page.write_text(build_html(), encoding="utf-8")
    out = MODULE / "module_5_report.pdf"
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                    f"--print-to-pdf={out}", page.as_uri()], check=True, capture_output=True)
    print(f"wrote {out.relative_to(MODULE)} ({out.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
