#!/usr/bin/env bash
# fresh_install_check.sh: prove module_5 installs and runs from a clean copy,
# once with pip and once with uv.
#
# EN 605.256 Modern Software Concepts in Python, Module 5.
# Joshua Latz (jlatz1)
#
# Each leg extracts module_5 from git into its own temporary directory (no
# .venv, no .env, no caches, nothing untracked), builds a venv the way the
# README's Fresh Install section says to, and then checks:
#   1. every src/ module imports from outside src/ (the editable install works)
#   2. pylint and pydeps run (the lock carries the tooling)
#   3. the suite passes without a database: pytest -m "not db and not integration"
# Coverage is off for that run, because the deselected database tests are
# what reach the remaining lines; the full gate enforces 100%.
#
# Usage (from any directory):
#   scripts/fresh_install_check.sh               check the HEAD commit
#   scripts/fresh_install_check.sh --worktree    check the working tree as it
#                                                would be committed (gate use)

set -uo pipefail

MODULE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO="$(git -C "$MODULE_DIR" rev-parse --show-toplevel)"
PYTHON="${PYTHON:-python3.14}"
MODULES="app, applicant_search, clean, db_safety, load_data, models, orm_queries, pull_data, query_data, scrape"

fail() { echo "FRESH INSTALL FAILED [$1]: $2" >&2; exit 1; }

case "${1:-}" in
    "") TREE="HEAD"; LABEL="HEAD ($(git -C "$REPO" rev-parse --short HEAD))" ;;
    --worktree)
        # Tree of the working tree with .gitignore respected, built in a
        # scratch index so the real index is untouched.
        IDX="$(mktemp)"
        cp "$(git -C "$REPO" rev-parse --absolute-git-dir)/index" "$IDX"
        GIT_INDEX_FILE="$IDX" git -C "$REPO" add -A >/dev/null 2>&1
        TREE="$(GIT_INDEX_FILE="$IDX" git -C "$REPO" write-tree)"
        rm -f "$IDX"
        LABEL="working tree ($TREE)"
        ;;
    *) echo "usage: $0 [--worktree]"; exit 2 ;;
esac

command -v "$PYTHON" >/dev/null || fail setup "$PYTHON not found"
command -v uv >/dev/null || fail setup "uv not found"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
echo "Fresh install check of $LABEL in $WORK"

extract() {  # $1: destination; leaves module_5 at $1/module_5
    mkdir -p "$1"
    git -C "$REPO" archive "$TREE" module_5 | tar -x -C "$1" || fail extract "git archive failed"
}

verify() {  # $1: leg name, $2: module_5 copy
    local leg="$1" dir="$2" py="$2/.venv/bin/python"
    (cd "$WORK" && "$py" -c "import $MODULES") >"$WORK/$leg-import.log" 2>&1 \
        || fail "$leg" "imports from outside src/ failed; $(tail -3 "$WORK/$leg-import.log")"
    "$py" -m pylint --version >/dev/null 2>&1 || fail "$leg" "pylint missing"
    "$dir/.venv/bin/pydeps" --version >/dev/null 2>&1 || fail "$leg" "pydeps missing"
    (cd "$dir" && "$py" -m pytest -m "not db and not integration" --no-cov -p no:cacheprovider) \
        >"$WORK/$leg-pytest.log" 2>&1 || { tail -20 "$WORK/$leg-pytest.log"; fail "$leg" "pytest failed"; }
    echo "  ok  $leg: $(grep -oE "[0-9]+ passed, [0-9]+ deselected" "$WORK/$leg-pytest.log")"
}

# pip leg
extract "$WORK/pip"
(
    cd "$WORK/pip/module_5" &&
    "$PYTHON" -m venv .venv &&
    .venv/bin/pip install -q -r requirements.txt &&
    .venv/bin/pip install -q -e . --no-deps
) >"$WORK/pip-install.log" 2>&1 || { tail -20 "$WORK/pip-install.log"; fail pip "install failed"; }
verify pip "$WORK/pip/module_5"

# uv leg
extract "$WORK/uv"
(
    cd "$WORK/uv/module_5" &&
    uv venv -q -p 3.14 .venv &&
    uv pip sync -q requirements.txt &&
    uv pip install -q -e . --no-deps
) >"$WORK/uv-install.log" 2>&1 || { tail -20 "$WORK/uv-install.log"; fail uv "install failed"; }
verify uv "$WORK/uv/module_5"

echo "FRESH INSTALL OK: pip and uv"
