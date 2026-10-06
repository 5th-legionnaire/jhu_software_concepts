#!/usr/bin/env bash
# snyk_scan.sh: scan every pinned package in requirements.txt with Snyk.
#
# EN 605.256 Modern Software Concepts in Python, Module 5.
# Joshua Latz (jlatz1)
#
# requirements.txt is a universal lock, and Snyk does not evaluate environment
# markers: it stops with "Missing required packages" for any line that does not
# apply to this machine. scripts/snyk_requirements.py splits the lock into the
# lines that apply here and the lines a marker excludes, and this script scans
# each group, the second in a scratch environment that installs just those pins,
# so none of the lock's packages goes unscanned.
#
# Run from module_5/ with the project environment active and `snyk` signed in:
#
#   scripts/snyk_scan.sh                    # human-readable output, for the screenshot
#   scripts/snyk_scan.sh --json DIR         # also write DIR/applies.json and DIR/excluded.json
#
# SNYK_THRESHOLD (default "high") is the lowest severity that fails the run, as
# `snyk test --severity-threshold` defines it. Exit status: 0 clean at that
# threshold, 1 a finding at or above it, 2 the scan itself could not run.

set -uo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."
THRESHOLD="${SNYK_THRESHOLD:-high}"
JSON_DIR=""
[ "${1:-}" = "--json" ] && { JSON_DIR="${2:?usage: snyk_scan.sh [--json DIR]}"; mkdir -p "$JSON_DIR"; JSON_DIR="$(cd "$JSON_DIR" && pwd)"; }

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$WORK/applies" "$WORK/excluded"
python scripts/snyk_requirements.py "$WORK/applies/requirements.txt" "$WORK/excluded/requirements.txt" || exit 2

status=0
scan() {  # $1: label, $2: directory holding requirements.txt, $3: python to inspect
    local label="$1" dir="$2" py="$3"
    echo "=== Snyk dependency scan: $label ($(grep -c . "$dir/requirements.txt") pinned packages)"
    (cd "$dir" && snyk test --file=requirements.txt --package-manager=pip --command="$py" \
        --severity-threshold="$THRESHOLD")
    local rc=$?
    if [ -n "$JSON_DIR" ]; then
        (cd "$dir" && snyk test --file=requirements.txt --package-manager=pip --command="$py" --json) \
            | python -c "import json,sys; d=json.load(sys.stdin); d=d[0] if isinstance(d,list) else d; d['path']='module_5'; json.dump(d, open('$JSON_DIR/$label.json','w'), indent=2)"
    fi
    [ "$rc" -gt "$status" ] && status="$rc"
    return 0
}

scan applies "$WORK/applies" "$(command -v python)"

if [ -s "$WORK/excluded/requirements.txt" ]; then
    python -m venv "$WORK/scratch-venv" >/dev/null 2>&1 \
        && "$WORK/scratch-venv/bin/python" -m pip install -q -r "$WORK/excluded/requirements.txt" >/dev/null 2>&1 \
        || { echo "could not build the scratch environment for the marker-excluded pins" >&2; exit 2; }
    scan excluded "$WORK/excluded" "$WORK/scratch-venv/bin/python"
fi

echo "=== Result: $([ "$status" -eq 0 ] && echo "no finding at or above '$THRESHOLD'" || echo "exit status $status")"
exit "$status"
