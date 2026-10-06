#!/usr/bin/env bash
# gate.sh: the Module 5 phase gate (PLAN.md section 3).
#
# EN 605.256 Modern Software Concepts in Python, Module 5.
# Joshua Latz (jlatz1)
#
# Usage (from any directory):
#   scripts/gate.sh entry <N>          standard entry checks E1 to E3 before phase N
#   scripts/gate.sh <N>                exit gate G1 to G9 for phase N
#   scripts/gate.sh log <N> "<notes>"  after the "M5 phase N" commit: append the
#                                      Gate Log row and mark the heading COMPLETE
#
# The exit gate fails fast and names the check that failed. On a pass it
# records the working tree's git tree hash in .gate/phase-N.pass; "log" refuses
# to run unless HEAD's tree is that exact tree, so the Gate Log can only ever
# describe a commit whose contents passed the gate.

set -uo pipefail

MODULE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO="$(git -C "$MODULE_DIR" rev-parse --show-toplevel)"
PY="$MODULE_DIR/.venv/bin/python"
M4_SRC="$REPO/module_4/src"
GATE_DIR="$MODULE_DIR/.gate"
PLAN="$MODULE_DIR/PLAN.md"
PY_VERSION="3.14.6"

cd "$MODULE_DIR" || exit 1
mkdir -p "$GATE_DIR"

fail() { echo "GATE FAILED [$1]: $2" >&2; exit 1; }
ok() { echo "  ok  $1  $2"; }

# Tree hash of the working tree as it would be committed (gitignore respected),
# computed in a scratch index so the real index is untouched.
worktree_tree() {
    local idx
    idx="$(mktemp)"
    cp "$(git -C "$REPO" rev-parse --absolute-git-dir)/index" "$idx"
    GIT_INDEX_FILE="$idx" git -C "$REPO" add -A >/dev/null 2>&1
    GIT_INDEX_FILE="$idx" git -C "$REPO" write-tree
    rm -f "$idx"
}

check_venv() {
    [ -x "$PY" ] || fail E3 "no venv at module_5/.venv"
    local version prefix
    version="$("$PY" -c 'import platform; print(platform.python_version())')"
    prefix="$("$PY" -c 'import sys; print(sys.prefix)')"
    [ "$version" = "$PY_VERSION" ] || fail E3 "venv Python is $version, expected $PY_VERSION"
    [ "$prefix" = "$MODULE_DIR/.venv" ] || fail E3 "venv prefix is $prefix"
    if [ -n "${VIRTUAL_ENV:-}" ] && [ "$VIRTUAL_ENV" != "$MODULE_DIR/.venv" ]; then
        fail E3 "a different venv is active: $VIRTUAL_ENV"
    fi
    ok E3 "module_5/.venv, Python $version"
}

# True when the Gate Log (section 11 of PLAN.md) has a row for phase $1. The
# search starts at that heading because earlier tables also have rows that
# begin "| 1 |", such as the Pylint message counts.
gate_log_has_row() {
    awk -v n="$1" '/^## 11\. Gate Log/ { in_log = 1 }
                   in_log && $0 ~ ("^\\| " n " \\|") { found = 1 }
                   END { exit !found }' "$PLAN"
}

pylint_score() {  # $1: output file
    grep -oE "rated at -?[0-9]+\.[0-9]+" "$1" | grep -oE -- "-?[0-9]+\.[0-9]+$"
}

# ---------------------------------------------------------------- entry
entry() {
    local n="$1"
    if [ "$n" -gt 0 ]; then
        local prev=$((n - 1)) subject
        subject="$(git -C "$REPO" log -1 --format=%s)"
        case "$subject" in "M5 phase $prev"*) ;; *) fail E1 "HEAD is '$subject', expected 'M5 phase $prev...'" ;; esac
        gate_log_has_row "$prev" || fail E1 "Gate Log has no row for phase $prev"
        ok E1 "phase $prev committed and logged"
    else
        ok E1 "phase 0 has no predecessor"
    fi
    [ -z "$(git -C "$REPO" status --porcelain)" ] || fail E2 "working tree is not clean"
    ok E2 "working tree clean"
    check_venv
    echo "ENTRY OK for phase $n. Phase-specific entry checks (E4) are listed in PLAN.md."
}

# ---------------------------------------------------------------- exit gate
gate() {
    local n="$1"
    echo "Gate for phase $n"
    check_venv

    # G1 + G2: full suite, coverage gate, strict markers, unmarked-test hook.
    local log="$GATE_DIR/phase-$n-pytest.log"
    "$PY" -m pytest >"$log" 2>&1
    local rc=$?
    grep -q "UsageError\|Every test needs one of the markers" "$log" && fail G2 "unmarked test(s); see $log"
    [ "$rc" -eq 0 ] || fail G1 "pytest exited $rc; see $log"
    local passed coverage
    passed="$(grep -oE "[0-9]+ passed" "$log" | tail -1 | grep -oE "[0-9]+")"
    coverage="$(grep -oE "Total coverage: [0-9.]+%" "$log" | grep -oE "[0-9.]+%")"
    grep -qE "[0-9]+ (failed|error)" "$log" && fail G1 "failures or errors in $log"
    ok G1 "$passed passed, coverage $coverage"
    ok G2 "collection hook accepted every test"

    # G3: Pylint non-regressing; exactly 10.00 with no messages from phase 6.
    local lint="$GATE_DIR/phase-$n-pylint.txt" score prev
    "$PY" -m pylint --rcfile=.pylintrc src >"$lint" 2>&1
    score="$(pylint_score "$lint")"
    [ -n "$score" ] || fail G3 "could not read a Pylint score; see $lint"
    [ -f "$GATE_DIR/scores" ] || fail G3 ".gate/scores has no baseline (PLAN.md Phase 0 task 8)"
    prev="$(grep -v "^phase-$n " "$GATE_DIR/scores" | tail -1 | awk '{print $2}')"
    awk -v s="$score" -v p="$prev" 'BEGIN { exit !(s + 0 >= p + 0) }' \
        || fail G3 "Pylint $score is below the previous gate's $prev"
    if [ "$n" -ge 6 ]; then
        [ "$score" = "10.00" ] || fail G3 "Pylint $score; phase 6 on requires 10.00"
        grep -qE "^src/.*: [CRWEF][0-9]{4}" "$lint" && fail G3 "Pylint messages remain; see $lint"
    fi
    ok G3 "Pylint $score (previous $prev)"

    # G4: every src/ module that Module 4 did not have lints clean on its own.
    local f new=0
    for f in src/*.py; do
        [ -e "$M4_SRC/$(basename "$f")" ] && continue
        new=$((new + 1))
        "$PY" -m pylint --rcfile=.pylintrc --fail-under=10 "$f" >"$GATE_DIR/new-file.txt" 2>&1 \
            || fail G4 "$f is new and not 10.00/10; see .gate/new-file.txt"
    done
    ok G4 "$new new src/ module(s), all 10.00/10"

    # G5: no inline disables.
    if grep -rn "pylint: disable" src; then fail G5 "inline pylint disable in src/"; fi
    ok G5 "no inline disables"

    # G6: .env untracked; no credential-shaped literals.
    if git -C "$MODULE_DIR" ls-files --error-unmatch .env >/dev/null 2>&1; then
        fail G6 ".env is tracked by git"
    fi
    "$PY" scripts/check_secrets.py "$n" || fail G6 "credential-shaped literal found"
    ok G6 ".env untracked, secrets scan clean"

    # G7: Change Register integrity.
    "$PY" scripts/check_change_register.py "$n" || fail G7 "Change Register incomplete"
    ok G7 "Change Register rows due by phase $n are complete"

    # G8: plan hygiene for the previous phase. This phase's row and heading
    # are written by "gate.sh log" after the commit, since the row records it.
    if [ "$n" -eq 0 ]; then
        grep -qE "^\| baseline \|" "$PLAN" || fail G8 "Gate Log has no baseline row"
    else
        local prev_n=$((n - 1))
        gate_log_has_row "$prev_n" || fail G8 "Gate Log has no row for phase $prev_n"
        grep -qE "^### Phase $prev_n:.*\(COMPLETE\)" "$PLAN" || fail G8 "phase $prev_n heading not marked COMPLETE"
    fi
    ok G8 "previous phase logged and marked"

    # G9: phase-specific exit checks.
    phase_checks "$n"

    printf "tree=%s\ntests=%s\ncoverage=%s\npylint=%s\n" \
        "$(worktree_tree)" "$passed" "$coverage" "$score" >"$GATE_DIR/phase-$n.pass"
    grep -v "^phase-$n " "$GATE_DIR/scores" >"$GATE_DIR/scores.tmp"
    echo "phase-$n $score" >>"$GATE_DIR/scores.tmp"
    mv "$GATE_DIR/scores.tmp" "$GATE_DIR/scores"
    echo "GATE PASSED for phase $n. Propose the commit 'M5 phase $n: <title>' to Josh, with the staged"
    echo "file list, and commit only on his approval. Then run: scripts/gate.sh log $n \"<notes>\""
}

phase_checks() {
    case "$1" in
    0)
        local snap
        for snap in tests/snapshots/m4_run_all.txt tests/snapshots/m4_orm_sql.txt; do
            [ -s "$snap" ] || fail G9 "missing or empty snapshot $snap"
        done
        ok G9 "parity snapshots present"

        # Every Module 4 test is still collected here (none lost in the copy).
        local m4_ids m5_ids missing
        m4_ids="$(cd "$REPO/module_4" && "$PY" -m pytest --collect-only --no-cov -p no:cacheprovider 2>/dev/null | grep "::" | sort)"
        m5_ids="$("$PY" -m pytest --collect-only --no-cov -p no:cacheprovider 2>/dev/null | grep "::" | sort)"
        missing="$(comm -23 <(echo "$m4_ids") <(echo "$m5_ids"))"
        [ "$(echo "$m4_ids" | grep -c "::")" -eq 102 ] || fail G9 "expected 102 Module 4 tests"
        [ -z "$missing" ] || fail G9 "Module 4 tests missing from module_5: $missing"
        ok G9 "all 102 Module 4 tests carried over and passing"

        # G2 must bite: an unmarked dummy test has to stop collection.
        local probe="tests/test_zz_gate_unmarked_probe.py" out
        printf '"""Gate probe; deleted by gate.sh."""\n\n\ndef test_probe():\n    assert True\n' >"$probe"
        out="$("$PY" -m pytest --collect-only --no-cov -p no:cacheprovider 2>&1)"
        local probe_rc=$?
        rm -f "$probe"
        [ "$probe_rc" -ne 0 ] && echo "$out" | grep -q "test_zz_gate_unmarked_probe.py::test_probe" \
            || fail G9 "an unmarked dummy test was not rejected (G2 does not bite)"
        ok G9 "unmarked dummy test rejected, then deleted"

        # /analysis renders against the local database from .env.
        PYTHONPATH=src "$PY" -c "
from app import create_app
response = create_app().test_client().get('/analysis')
assert response.status_code == 200, response.status_code
assert 'Q1' in response.get_data(as_text=True)
" >/dev/null 2>&1 || fail G9 "/analysis did not render against the local database"
        ok G9 "/analysis renders against the local database"
        ;;
    1)
        # Every requirement line in the lock is an exact pin.
        local pins reqs
        pins="$(grep -c "==" requirements.txt)"
        reqs="$(grep -cvE '^[[:space:]]*(#|$)' requirements.txt)"
        [ "$pins" -eq "$reqs" ] || fail G9 "requirements.txt: $pins pins but $reqs requirement lines"
        ok G9 "requirements.txt pins all $reqs lines"

        # This venv uses the editable install, not a path edit.
        "$PY" -m pip show gradcafe-analytics >/dev/null 2>&1 \
            || fail G9 "gradcafe-analytics is not installed in module_5/.venv (pip install -e . --no-deps)"
        ok G9 "editable install present in module_5/.venv"

        # Both installers build a working environment from a clean copy of
        # what is about to be committed.
        scripts/fresh_install_check.sh --worktree >"$GATE_DIR/phase-1-fresh.log" 2>&1 \
            || fail G9 "fresh_install_check.sh failed; see .gate/phase-1-fresh.log"
        ok G9 "fresh install passes with pip and uv"
        ;;
    2)
        # No Module 3 variable survives in code, tests, or the Sphinx docs.
        if grep -rn "PG\(HOST\|USER\|PASSWORD\|DATABASE\|PORT\)" src tests docs; then
            fail G9 "a retired PG* variable is still referenced"
        fi
        ok G9 "no PG* reference in src, tests, or docs"

        [ -f .env.example ] || fail G9 ".env.example is missing"
        git -C "$MODULE_DIR" check-ignore -q .env || fail G9 ".env is not gitignored"
        git -C "$MODULE_DIR" check-ignore -q .env.example && fail G9 ".env.example is gitignored"
        ok G9 ".env.example tracked, .env ignored"

        # The app reads its database settings from .env alone: run it with a
        # cleared environment, so nothing can come from the shell.
        env -i HOME="$HOME" PATH="$PATH" PYTHONPATH=src "$PY" -c "
from app import create_app
response = create_app().test_client().get('/analysis')
assert response.status_code == 200, response.status_code
assert 'Q1' in response.get_data(as_text=True)
" >/dev/null 2>&1 || fail G9 "the app did not start from .env with an empty shell environment"
        ok G9 "app renders /analysis from .env with an empty shell environment"

        # A clean copy has no .env, so the offline tests must pass with no
        # database configured at all (the fresh-install check does exactly that).
        scripts/fresh_install_check.sh --worktree >"$GATE_DIR/phase-$1-fresh.log" 2>&1 \
            || fail G9 "fresh_install_check.sh failed; see .gate/phase-$1-fresh.log"
        ok G9 "fresh install passes with pip and uv, no .env, no database configured"
        ;;
    3)
        # The SQL guard and the parity proof, by name, so a deselected or
        # renamed test cannot let the phase pass.
        "$PY" -m pytest --no-cov -p no:cacheprovider \
            "tests/test_sql_guard.py::test_no_sql_string_building" \
            "tests/test_query_data.py::test_parity_with_module_4" >"$GATE_DIR/phase-3-exit.log" 2>&1 \
            || fail G9 "the AST guard or the parity test failed; see .gate/phase-3-exit.log"
        ok G9 "AST guard reports zero findings and parity with Module 4 holds"

        # The guard must bite: reintroduce an f-string SQL statement, confirm
        # the guard fails and names the file, then delete it.
        local probe="src/zz_gate_probe.py" out
        printf '"""Gate probe; deleted by gate.sh."""\n\n\ndef probe(table):\n    return f"SELECT * FROM {table}"\n' >"$probe"
        out="$("$PY" -m pytest --no-cov -p no:cacheprovider tests/test_sql_guard.py::test_no_sql_string_building 2>&1)"
        local probe_rc=$?
        rm -f "$probe"
        [ "$probe_rc" -ne 0 ] && echo "$out" | grep -q "zz_gate_probe.py" \
            || fail G9 "an f-string SQL statement was not caught (the guard does not bite)"
        ok G9 "guard rejected a reintroduced f-string SQL statement, then the probe was deleted"
        ;;
    4)
        # The matrix is parametrized, not a handful of hand-written cases.
        local matrix
        matrix="$("$PY" -m pytest tests/test_sqli_malicious.py --collect-only --no-cov -p no:cacheprovider 2>/dev/null | grep -c "::")"
        [ "$matrix" -ge 45 ] || fail G9 "the malicious-input matrix has only $matrix cases (expected at least 45)"
        ok G9 "malicious-input matrix: $matrix parametrized cases"

        # The route exists and answers JSON, from a cleared environment.
        env -i HOME="$HOME" PATH="$PATH" PYTHONPATH=src "$PY" -c "
from app import create_app
client = create_app(testing=True).test_client()
response = client.get('/api/applicants?limit=1000000')
body = response.get_json()
assert response.status_code == 200, response.status_code
assert body['limit'] == 100 and body['clamped'] is True and body['count'] <= 100, body
assert client.get('/api/applicants?debug=1').status_code == 400
" >/dev/null 2>&1 || fail G9 "GET /api/applicants did not clamp and reject as specified"
        ok G9 "GET /api/applicants clamps a huge limit and rejects an unknown parameter"
        ;;
    5)
        # The real credentials in .env appear nowhere they should not.
        "$PY" scripts/check_credential_leaks.py >"$GATE_DIR/phase-5-leaks.log" 2>&1 \
            || fail G9 "a password from .env leaked; see .gate/phase-5-leaks.log"
        ok G9 "no password from .env is in the tree, git history, server log, or shell history"

        # The account in .env is the least-privilege one, and the app and the
        # pull path work as it, from a cleared environment so nothing comes
        # from the shell. The pull re-sends a row that is already present:
        # ON CONFLICT DO NOTHING still needs INSERT, and no data is written.
        env -i HOME="$HOME" PATH="$PATH" PYTHONPATH=src "$PY" -c "
from psycopg import sql
from app import create_app
from load_data import create_connection, get_db_config
import pull_data

config = get_db_config()
assert config['user'] == 'gradcafe_app', 'DB_USER in .env is not gradcafe_app'
connection = create_connection(config)
with connection.cursor() as cursor:
    cursor.execute(sql.SQL('SELECT rolsuper, rolcreaterole, rolcreatedb FROM pg_roles WHERE rolname = current_user LIMIT 1'))
    assert cursor.fetchone() == (False, False, False), 'the .env account has elevated attributes'
    cursor.execute(sql.SQL('SELECT url, (SELECT COUNT(*) FROM applicants) FROM applicants ORDER BY p_id LIMIT 1'))
    url, before = cursor.fetchone()
connection.close()

assert create_app(testing=True).test_client().get('/analysis').status_code == 200
added = pull_data.load_records([{'url': url}], connect=lambda: create_connection(config))
assert added == 0, 'a re-sent row must not be inserted twice'
connection = create_connection(config)
with connection.cursor() as cursor:
    cursor.execute(sql.SQL('SELECT COUNT(*) FROM applicants LIMIT 1'))
    assert cursor.fetchone()[0] == before, 'the row count changed'
connection.close()
" >"$GATE_DIR/phase-5-account.log" 2>&1 \
            || fail G9 "the .env account failed the least-privilege checks; see .gate/phase-5-account.log"
        ok G9 ".env account is gradcafe_app, not a superuser; /analysis renders; a pull works and writes nothing"

        [ -s privileges.txt ] && grep -q "gradcafe_app" privileges.txt && ! grep -q "SCRAM" privileges.txt \
            || fail G9 "privileges.txt is missing, or holds a verifier"
        [ "$(head -c 8 privileges.png 2>/dev/null | od -An -tx1 | tr -d ' ')" = "89504e470d0a1a0a" ] \
            || fail G9 "privileges.png is missing or is not a PNG"
        ok G9 "privileges.txt free of verifiers; privileges.png present and a valid PNG"
        ;;
    6)
        # The committed report is the real output, and it is exactly 10.00 with no message.
        [ -s pylint_report.txt ] || fail G9 "pylint_report.txt is missing"
        grep -q "rated at 10.00/10" pylint_report.txt || fail G9 "pylint_report.txt does not show 10.00/10"
        grep -qE "^src/.*: [CRWEF][0-9]{4}" pylint_report.txt && fail G9 "pylint_report.txt lists messages"
        "$PY" -m pylint --rcfile=.pylintrc --fail-under=10 src >"$GATE_DIR/phase-6-pylint-run.txt" 2>&1 \
            || fail G9 "pylint --fail-under=10 failed; see .gate/phase-6-pylint-run.txt"
        ok G9 "pylint_report.txt shows 10.00/10 with no messages, and a fresh run agrees"

        # The compiled ORM SQL is Module 4's plus exactly the Phase 3 LIMIT, and the
        # analysis answers are unchanged.
        "$PY" -m pytest --no-cov -p no:cacheprovider -q \
            tests/test_orm_queries.py::test_compiled_sql_unchanged \
            tests/test_query_data.py::test_parity_with_module_4 >"$GATE_DIR/phase-6-parity.log" 2>&1 \
            || fail G9 "the ORM SQL or the analysis answers changed; see .gate/phase-6-parity.log"
        ok G9 "ORM SQL is Module 4's plus one LIMIT; run_all still matches the Module 4 snapshot"

        # No escape hatches: no disable anywhere in src, a pylintrc of two entries.
        [ "$(grep -cE '^[a-z-]+=' .pylintrc)" -eq 2 ] || fail G9 ".pylintrc holds more than the two permitted entries"
        ok G9 ".pylintrc holds exactly the source root and the SQLAlchemy classification"
        ;;
    7)
        # The same validation the CI dependency-graph job runs (R30).
        command -v dot >/dev/null || fail G9 "Graphviz's dot is not installed (brew install graphviz)"
        test -s dependency.svg && grep -q "<svg" dependency.svg || fail G9 "dependency.svg is empty or not an SVG"
        local missing=""
        for module in app applicant_search clean db_safety load_data models orm_queries pull_data query_data scrape; do
            name="$module"; [ "$module" = "app" ] && name="app_py"
            grep -q "<title>$name</title>" dependency.svg || missing="$missing $module"
        done
        [ -z "$missing" ] || fail G9 "dependency.svg is missing:$missing"
        ok G9 "dependency.svg is a valid SVG naming all ten src/ modules, both new ones included"

        # Regenerate with the documented command: the committed graph must be current.
        "$PY" -m pydeps src/app.py --noshow -T svg -o "$GATE_DIR/regenerated.svg" --max-module-depth=1 >/dev/null 2>&1 \
            || fail G9 "pydeps failed to regenerate the graph"
        [ "$(grep -o '<title>[^<]*</title>' dependency.svg | sort | md5)" = "$(grep -o '<title>[^<]*</title>' "$GATE_DIR/regenerated.svg" | sort | md5)" ] \
            || fail G9 "dependency.svg is stale: regenerate it with the command in the README"
        ok G9 "the committed graph matches a fresh pydeps run"

        grep -q -- "--max-module-depth=1" README.md && grep -q -- "--max-module-depth=1" report/dependency_summary.md \
            || fail G9 "the final pydeps flags are not recorded in the README and the summary"
        ok G9 "the flags are recorded in the README and the summary"
        ;;
    8)
        # The scan, run live now: every pinned package, nothing at or above "high".
        command -v snyk >/dev/null && snyk whoami --experimental >/dev/null 2>&1 \
            || fail G9 "snyk is not installed or not signed in (snyk auth)"
        scripts/snyk_scan.sh >"$GATE_DIR/phase-8-snyk.log" 2>&1 \
            || fail G9 "snyk found an issue at or above high, or could not scan; see .gate/phase-8-snyk.log"
        grep -q "no vulnerable paths found" "$GATE_DIR/phase-8-snyk.log" \
            || fail G9 "the Snyk run did not report a clean result"
        ok G9 "a live Snyk scan of all 70 pinned packages finds nothing at or above high"

        # The committed evidence agrees, and the screenshots are real PNGs.
        "$PY" -c "
import json
for name in ('snyk_report.json', 'snyk/excluded.json'):
    d = json.load(open(name))
    assert d['ok'] is True and d['vulnerabilities'] == [], name
before = json.load(open('snyk/before_upgrade_applies.json'))
assert before['vulnerabilities'], 'the before-upgrade record is empty'
" || fail G9 "the committed Snyk evidence is not a clean result with a before record"
        local png
        for png in snyk-analysis.png snyk-code-analysis.png; do
            [ "$(head -c 8 "$png" 2>/dev/null | od -An -tx1 | tr -d ' ')" = "89504e470d0a1a0a" ] \
                || fail G9 "$png is missing or is not a PNG (a screenshot of the scan)"
        done
        ok G9 "evidence committed: clean report, before-upgrade record, both screenshots"
        [ -s report/snyk_triage.md ] && [ -s snyk_code_report.txt ] || fail G9 "the triage or the Snyk Code report is missing"
        ok G9 "triage table and Snyk Code report present"
        ;;
    9)
        [ -s ../.github/workflows/ci.yml ] || fail G9 ".github/workflows/ci.yml is missing"
        "$PY" -m pytest tests/test_ci_config.py --no-cov -p no:cacheprovider -q >"$GATE_DIR/phase-9-ci-config.log" 2>&1 \
            || fail G9 "ci.yml no longer enforces what the assignment requires; see .gate/phase-9-ci-config.log"
        ok G9 "ci.yml parses and every required gate is present (offline stage)"
        git -C "$REPO" diff --quiet "1ecf2c9" -- .github/workflows/tests.yml \
            || fail G9 "Module 4's tests.yml was modified"
        ok G9 "tests.yml is byte-identical to the Module 4 baseline"

        if [ "${GATE_CI_LIVE:-0}" = "1" ]; then
            # Live stage: the pushed commit's run of ci.yml must have succeeded, in all four jobs.
            command -v gh >/dev/null || fail G9 "gh is not installed"
            local sha run
            sha="$(git -C "$REPO" rev-parse HEAD)"
            run="$(gh run list --workflow ci.yml --commit "$sha" --json conclusion,databaseId --jq '.[0]' 2>/dev/null)"
            [ -n "$run" ] || fail G9 "no ci.yml run found for $sha; push first"
            echo "$run" | grep -q '"conclusion":"success"' || fail G9 "the ci.yml run for $sha did not succeed: $run"
            local id jobs
            id="$(echo "$run" | "$PY" -c "import json,sys; print(json.load(sys.stdin)['databaseId'])")"
            jobs="$(gh run view "$id" --json jobs --jq '[.jobs[] | select(.conclusion=="success")] | length')"
            [ "$jobs" -ge 5 ] || fail G9 "expected 5 green jobs (lint, dependency-graph, snyk, test on pip and uv), found $jobs"
            ok G9 "ci.yml run $id for $sha: success, $jobs green jobs"
            ! cmp -s actions_success.png ../module_4/actions_success.png \
                || fail G9 "actions_success.png is still Module 4's screenshot"
            [ "$(head -c 8 actions_success.png | od -An -tx1 | tr -d ' ')" = "89504e470d0a1a0a" ] || fail G9 "actions_success.png is not a PNG"
            ok G9 "actions_success.png is a PNG and is not Module 4's"
        else
            echo "  --  G9  live stage skipped (run GATE_CI_LIVE=1 scripts/gate.sh 9 after the first green run)"
        fi
        ;;
    10)
        # The Sphinx docs build with every warning treated as an error, so Read the
        # Docs can fail on warnings too.
        rm -rf docs/_build
        "$PY" -m sphinx -W -q -b html docs docs/_build/html >"$GATE_DIR/phase-10-sphinx.log" 2>&1 \
            || fail G9 "the Sphinx build has warnings or errors; see .gate/phase-10-sphinx.log"
        ok G9 "Sphinx builds with no warnings (-W)"

        # The report exists, is a PDF, and its test count matches the evidence.
        [ "$(head -c 4 module_5_report.pdf 2>/dev/null)" = "%PDF" ] || fail G9 "module_5_report.pdf is missing or not a PDF"
        grep -q "$passed passed" coverage_summary.txt \
            || fail G9 "coverage_summary.txt does not show this run's $passed tests; regenerate it, then the report"
        ok G9 "module_5_report.pdf present; coverage_summary.txt matches this run ($passed passed)"

        # Every file the README links to exists.
        "$PY" - <<'PYCHECK' || fail G9 "the README links to a file that does not exist"
import os, re, sys
text = open("README.md", encoding="utf-8").read()
missing = sorted({f for f in re.findall(r"\]\((?!http|#)([^)#]+)", text) if not os.path.exists(f)})
print("missing:", missing) if missing else None
sys.exit(1 if missing else 0)
PYCHECK
        ok G9 "every file the README links to exists"
        ;;
    11)
        grep -q "configuration: module_5/docs/conf.py" ../.readthedocs.yaml \
            && grep -q "requirements: module_5/requirements.txt" ../.readthedocs.yaml \
            || fail G9 ".readthedocs.yaml does not build module_5"
        ok G9 ".readthedocs.yaml builds module_5/docs from module_5/requirements.txt"
        [ "$(git -C "$REPO" rev-parse 'module-4-final^{commit}' 2>/dev/null | cut -c1-7)" = "1ecf2c9" ] \
            || fail G9 "tag module-4-final does not point at 1ecf2c9"
        git -C "$REPO" ls-remote --tags origin module-4-final | grep -q module-4-final \
            || fail G9 "tag module-4-final is not on GitHub"
        git -C "$REPO" show module-4-final:.readthedocs.yaml | grep -q "module_4/docs/conf.py" \
            || fail G9 "at module-4-final, .readthedocs.yaml does not build module_4"
        ok G9 "module-4-final is on GitHub at 1ecf2c9, and builds module_4's docs there"
        rm -rf docs/_build
        "$PY" -m sphinx -W -q -b html docs docs/_build/html >"$GATE_DIR/phase-11-sphinx.log" 2>&1 \
            || fail G9 "the Sphinx build that Read the Docs will run has warnings; see .gate/phase-11-sphinx.log"
        ok G9 "the docs Read the Docs will build are clean under -W"
        ;;
    *)
        echo "  --  G9  no phase-specific checks defined for phase $1 yet"
        ;;
    esac
}

# ---------------------------------------------------------------- log
log_row() {
    local n="$1" notes="$2" pass="$GATE_DIR/phase-$1.pass"
    [ -f "$pass" ] || fail G8 "no recorded gate pass for phase $n; run scripts/gate.sh $n"
    local subject tree
    subject="$(git -C "$REPO" log -1 --format=%s)"
    case "$subject" in "M5 phase $n"*) ;; *) fail G8 "HEAD is '$subject', not the phase $n commit" ;; esac
    tree="$(git -C "$REPO" rev-parse 'HEAD^{tree}')"
    [ "$tree" = "$(grep '^tree=' "$pass" | cut -d= -f2)" ] \
        || fail G8 "HEAD's contents differ from what passed the gate; rerun scripts/gate.sh $n"
    gate_log_has_row "$n" && fail G8 "Gate Log already has a row for phase $n"
    local commit when tests coverage pylint
    commit="$(git -C "$REPO" rev-parse --short HEAD)"
    when="$(TZ=America/New_York date "+%Y-%m-%d %H:%M")"
    tests="$(grep '^tests=' "$pass" | cut -d= -f2)"
    coverage="$(grep '^coverage=' "$pass" | cut -d= -f2)"
    pylint="$(grep '^pylint=' "$pass" | cut -d= -f2)"
    # Heading first: a failure here leaves PLAN.md without a row, so a rerun is clean.
    sed -i.bak -E "/^### Phase $n: /{/\(COMPLETE\)\$/!s/\$/ (COMPLETE)/;}" "$PLAN" && rm -f "$PLAN.bak"
    grep -qE "^### Phase $n:.*\(COMPLETE\)\$" "$PLAN" || fail G8 "could not mark the phase $n heading"
    echo "| $n | $when | $commit | $tests | $coverage | $pylint | $notes |" >>"$PLAN"
    echo "Gate Log row appended for phase $n ($commit). Propose the commit 'M5 phase $n: gate log' to Josh."
}

case "${1:-}" in
    entry) [ $# -eq 2 ] || { echo "usage: $0 entry <N>"; exit 2; }; entry "$2" ;;
    log)   [ $# -eq 3 ] || { echo "usage: $0 log <N> \"<notes>\""; exit 2; }; log_row "$2" "$3" ;;
    ''|*[!0-9]*) echo "usage: $0 <N> | entry <N> | log <N> \"<notes>\""; exit 2 ;;
    *)     gate "$1" ;;
esac
