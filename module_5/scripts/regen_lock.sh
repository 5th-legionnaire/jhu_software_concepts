#!/usr/bin/env bash
# regen_lock.sh: regenerate requirements.txt, the fully pinned lock, from setup.py.
#
# EN 605.256 Modern Software Concepts in Python, Module 5.
# Joshua Latz (jlatz1)
#
# setup.py is the only place dependencies are edited (decision D7). This lock
# pins every package the runtime and the "dev" extra need, transitive ones
# included, because "uv pip sync" installs exactly the file and resolves
# nothing. The lock is universal (platform markers, not this machine's
# platform), so the same file serves macOS, the Linux CI runner, and Windows.
# Hashes are omitted: "pip install -r" with hashes would also demand them for
# the editable "pip install -e ." that follows.
#
# Usage (from any directory):  scripts/regen_lock.sh

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
uv pip compile setup.py --extra dev --universal --python-version 3.14 \
    --custom-compile-command "scripts/regen_lock.sh" -o requirements.txt
