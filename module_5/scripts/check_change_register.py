"""check_change_register.py: gate check G7, Change Register integrity.

EN 605.256 Modern Software Concepts in Python, Module 5.
Joshua Latz (jlatz1)

Fails unless every CHANGES.md row whose phase is at most N is marked done,
states a rationale, has its chg-XX anchor in README.md, and names tests that
pytest actually collects. A register entry that points at a test which does
not exist is worse than no entry, because it reads as verified.

Contains:
    Parsing:    parse_register(), extract_test_refs()
    Resolution: collected_node_ids(), resolves()
    Entry:      main()

Usage (from module_5/):
    python scripts/check_change_register.py <phase>
"""

import fnmatch
import os
import re
import subprocess
import sys

MODULE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REGISTER = os.path.join(MODULE_DIR, "CHANGES.md")
README = os.path.join(MODULE_DIR, "README.md")
COLUMNS = ("id", "phase", "status", "change", "rationale", "verified")
TEST_FILE = re.compile(r"^test_\w+\.py$")


def parse_register(path):
    """Return the register rows as dicts keyed by COLUMNS.

    Args:
        path: CHANGES.md path.

    Returns:
        list[dict]: one dict per CHG row, in file order.
    """
    rows = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            if not line.startswith("| CHG-"):
                continue
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            if len(cells) != len(COLUMNS):
                sys.exit(f"Malformed register row ({len(cells)} cells): {line.strip()}")
            rows.append(dict(zip(COLUMNS, cells)))
    return rows


def extract_test_refs(verified):
    """Extract (file, name) test references from a Verified by cell.

    A backticked ``file.py::name`` sets the current file; ``::name`` reuses it;
    a bare ``test_x.py`` becomes (file, "*"). Other backticked text (scripts,
    screenshots) is evidence, not a test reference, and is skipped.

    Args:
        verified: the cell text.

    Returns:
        list[tuple[str, str]]: references in cell order.
    """
    refs, current = [], None
    for token in re.findall(r"`([^`]+)`", verified):
        if "::" in token:
            head, name = token.split("::", 1)
            current = head or current
            if current is None:
                sys.exit(f"'::{name}' has no preceding file in: {verified}")
            refs.append((current, name))
        elif TEST_FILE.match(token):
            current = token
            refs.append((token, "*"))
    return refs


def collected_node_ids():
    """Node IDs from a collect-only pytest run in module_5/, coverage off.

    No -q is passed: pytest.ini's addopts already has one, and a second turns
    the node ID listing into per-file counts.

    Returns:
        list[str]: node IDs such as ``tests/test_x.py::test_y[param]``.
    """
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "--no-cov",
         "-p", "no:cacheprovider"],
        cwd=MODULE_DIR, capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        sys.exit(f"pytest collection failed:\n{result.stdout}{result.stderr}")
    return [line.strip() for line in result.stdout.splitlines() if "::" in line]


def resolves(ref, node_ids):
    """True when at least one collected test matches the reference.

    ``[`` is escaped so that ``name[*]`` means "any parameter ID" rather than
    an fnmatch character class. A reference without brackets also matches the
    parametrized instances of that test.

    Args:
        ref: (file basename, test name pattern).
        node_ids: collected node IDs.

    Returns:
        bool: whether the reference names a real test.
    """
    file_name, pattern = ref
    pattern = pattern.replace("[", "[[]")
    for node in node_ids:
        node_file, node_name = node.split("::", 1)
        if os.path.basename(node_file) != file_name:
            continue
        if fnmatch.fnmatchcase(node_name, pattern) or \
                fnmatch.fnmatchcase(node_name.split("[", 1)[0], pattern):
            return True
    return False


def main():
    """Check every row due by the phase given on the command line."""
    if len(sys.argv) != 2 or not sys.argv[1].isdigit():
        sys.exit(__doc__)
    phase = int(sys.argv[1])
    rows = parse_register(REGISTER)
    ids = [row["id"] for row in rows]
    problems = [f"duplicate ID {i}" for i in sorted(set(ids)) if ids.count(i) > 1]
    with open(README, encoding="utf-8") as handle:
        readme = handle.read()
    due = [row for row in rows if int(row["phase"]) <= phase]
    node_ids = collected_node_ids() if due else []
    for row in due:
        cid = row["id"]
        anchor = cid.lower()
        if row["status"] != "done":
            problems.append(f"{cid}: status is '{row['status']}', not 'done'")
        if not row["rationale"]:
            problems.append(f"{cid}: no rationale")
        if not re.search(rf"""id=["']{anchor}["']""", readme):
            problems.append(f"{cid}: README.md has no '{anchor}' anchor")
        refs = extract_test_refs(row["verified"])
        if not refs and not row["verified"].startswith("Evidence:"):
            problems.append(f"{cid}: no test reference and no 'Evidence:' statement")
        for ref in refs:
            if not resolves(ref, node_ids):
                problems.append(f"{cid}: test '{ref[0]}::{ref[1]}' is not collected")
    if problems:
        print("Change Register check FAILED:")
        for problem in problems:
            print(f"  {problem}")
        sys.exit(1)
    print(f"Change Register OK: {len(due)} row(s) due by phase {phase}, "
          f"{len(rows)} registered.")


if __name__ == "__main__":
    main()
