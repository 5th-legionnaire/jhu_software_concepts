"""check_secrets.py: gate check G6, no credential-shaped literal in src/ or tests/.

EN 605.256 Modern Software Concepts in Python, Module 5.
Joshua Latz (jlatz1)

A pattern scan, not a proof: it catches the shapes a credential takes when it
is pasted into code (a password inside a connection URL, a password assigned a
literal in application code, a private key block, a cloud or SaaS token), so a
slip fails the gate before it reaches a commit.

Known exceptions are listed in KNOWN_EXCEPTIONS with the phase that removes
them. From that phase on the exception stops being honored, so a temporary
allowance cannot quietly become permanent.

Contains:
    Scanning: scan_file(), is_placeholder()
    Entry:    main()

Usage (from module_5/):
    python scripts/check_secrets.py <phase>
"""

import os
import re
import sys

MODULE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCAN_DIRS = ("src", "tests", "sql")
SCAN_SUFFIXES = (".py", ".html", ".js", ".ini", ".cfg", ".toml", ".yml", ".yaml", ".txt", ".sql")

# A password embedded in a URL: scheme://user:password@host
URL_PASSWORD = re.compile(r"[a-z][a-z0-9+.-]*://[^\s:/@\"']+:([^\s@\"']+)@", re.IGNORECASE)
# A password given a literal value; applied to src/ only, since tests build
# throwaway configs on purpose.
PASSWORD_LITERAL = re.compile(
    r"""(?i)\bpass(?:word|wd)?["']?\s*[:=]\s*["']([^"'\s]+)["']""")
# psql's :'name' syntax substitutes a variable, so PASSWORD :'name' carries no
# literal. Only this exact form is exempt from the literal check.
PSQL_VARIABLE = re.compile(r"(?i)\bPASSWORD\s+:'\w+'")
TOKEN_SHAPES = {
    "private key block": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "password literal in SQL": re.compile(r"(?i)\bPASSWORD\s+'[^']+'"),
    "AWS access key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "GitHub token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b"),
    "Snyk or other UUID API token assigned to a name": re.compile(
        r"(?i)(?:token|api[_-]?key|secret)\w*\s*[:=]\s*[\"'][0-9a-f]{8}-[0-9a-f]{4}-"
        r"[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}[\"']"),
}
# Values that are obviously not real: documentation placeholders, and
# references to a variable rather than a value (an env var name such as
# PGPASSWORD, a shell or format-string reference).
PLACEHOLDER = re.compile(
    r"^(?:pass|change-me|<[^>]+>|[A-Z][A-Z0-9_]*|\$\{?\w+\}?|%\(\w+\)s|\*+|\.\.\.)$")

# (path relative to module_5, exact literal, phase that removes it, why it exists)
KNOWN_EXCEPTIONS = [
    ("tests/conftest.py",
     "postgresql+psycopg://postgres:postgres@localhost:5432/gradcafe_test",
     2,
     "Module 4's local test-database fallback; Phase 2 moves tests to env-only URLs"),
]


def is_placeholder(value):
    """True for values that are clearly placeholders, never real credentials."""
    return bool(PLACEHOLDER.match(value))


def scan_file(path, rel, phase):
    """Return findings for one file as 'rel:line: description' strings.

    Args:
        path: absolute file path.
        rel: path relative to module_5, used for reporting and exceptions.
        phase: the phase being gated, which decides which exceptions still hold.

    Returns:
        list[str]: findings.
    """
    allowed = [lit for (p, lit, until, _why) in KNOWN_EXCEPTIONS if p == rel and phase < until]
    findings = []
    with open(path, encoding="utf-8", errors="replace") as handle:
        for number, line in enumerate(handle, start=1):
            if any(lit in line for lit in allowed):
                continue
            for match in URL_PASSWORD.finditer(line):
                if not is_placeholder(match.group(1)):
                    findings.append(f"{rel}:{number}: password embedded in a URL")
            if rel.startswith("src" + os.sep) and not PSQL_VARIABLE.search(line):
                for match in PASSWORD_LITERAL.finditer(line):
                    if not is_placeholder(match.group(1)):
                        findings.append(f"{rel}:{number}: password assigned a literal")
            for label, pattern in TOKEN_SHAPES.items():
                if pattern.search(line):
                    findings.append(f"{rel}:{number}: {label}")
    return findings


def main():
    """Scan src/ and tests/ and exit non-zero on any finding."""
    if len(sys.argv) != 2 or not sys.argv[1].isdigit():
        sys.exit(__doc__)
    phase = int(sys.argv[1])
    findings, scanned = [], 0
    for top in SCAN_DIRS:
        for root, dirs, files in os.walk(os.path.join(MODULE_DIR, top)):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for name in files:
                if name.endswith(SCAN_SUFFIXES):
                    path = os.path.join(root, name)
                    scanned += 1
                    findings += scan_file(path, os.path.relpath(path, MODULE_DIR), phase)
    if findings:
        print("Secrets check FAILED:")
        for finding in findings:
            print(f"  {finding}")
        sys.exit(1)
    honored = [e for e in KNOWN_EXCEPTIONS if phase < e[2]]
    print(f"Secrets check OK: {scanned} files scanned, "
          f"{len(honored)} time-boxed exception(s) honored.")
    for rel, _lit, until, why in honored:
        print(f"  {rel} (until phase {until}): {why}")


if __name__ == "__main__":
    main()
