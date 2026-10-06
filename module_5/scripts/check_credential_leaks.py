"""check_credential_leaks.py: prove the passwords in .env appear nowhere they should not.

EN 605.256 Modern Software Concepts in Python, Module 5.
Joshua Latz (jlatz1)

check_secrets.py looks for credential-shaped text in the code. This asks the
opposite question about the real credentials: it reads each password out of
.env and searches every place one could have leaked to, which is only
checkable with the actual values.

    the working tree         every file but .env itself, the venv, and caches
    git history              every commit, found with git grep so no password is an argument
    the PostgreSQL log       a failed statement is written there
    shell and psql history   a password typed on a command line is recorded there

Output is counts and labels only. A password is never printed, and is never
placed on a command line: git grep reads its patterns from a private file that
is deleted immediately afterwards.

Contains:
    credentials():  the passwords .env holds
    scan():         search a set of places for them
    main():         the gate check

Usage (from module_5/):
    python scripts/check_credential_leaks.py
"""

import os
import pathlib
import subprocess
import sys
import tempfile
from urllib import parse

MODULE_DIR = pathlib.Path(__file__).resolve().parent.parent
REPO_DIR = MODULE_DIR.parent
SKIPPED_DIRS = {".venv", "__pycache__", ".pytest_cache", ".git", "_build", "node_modules"}
PLACEHOLDERS = {"change-me", "choose-one", "yourpassword"}
MIN_LENGTH = 8   # shorter values match innocent text and prove nothing


def credentials(env_path):
    """Return the distinct passwords in a .env file, without their names.

    Reads every ``*PASSWORD`` variable and the password inside every ``*_URL``.

    Args:
        env_path: path to the .env file.

    Returns:
        set[str]: passwords long enough to search for, placeholders excluded.
    """
    found = set()
    for line in pathlib.Path(env_path).read_text(encoding="utf-8").splitlines():
        if "=" not in line or line.lstrip().startswith("#"):
            continue
        name, value = (part.strip() for part in line.split("=", 1))
        if name.endswith("PASSWORD"):
            found.add(value)
        elif name.endswith("_URL"):
            found.add(parse.unquote(parse.urlsplit(value).password or ""))
    return {value for value in found if len(value) >= MIN_LENGTH and value not in PLACEHOLDERS}


def _files(root, skip_names):
    for path in pathlib.Path(root).rglob("*"):
        if path.is_file() and not SKIPPED_DIRS & set(path.parts) and path.name not in skip_names:
            yield path


def scan(passwords, trees, extra_files, skip_names=(".env",)):
    """Count the files that contain any of the passwords, by place.

    Args:
        passwords: the cleartext values to look for.
        trees: directories searched recursively.
        extra_files: individual files, such as logs and history files.
        skip_names: file names never searched, because they are meant to hold them.

    Returns:
        dict[str, tuple[int, int]]: label -> (files scanned, files that matched).
    """
    def matches(path):
        try:
            text = pathlib.Path(path).read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return None
        return any(password in text for password in passwords)

    report = {}
    for tree in trees:
        results = [matches(path) for path in _files(tree, skip_names)]
        results = [r for r in results if r is not None]
        report[f"files under {pathlib.Path(tree).name}/"] = (len(results), sum(results))
    extras = [r for r in (matches(path) for path in extra_files) if r is not None]
    report["logs and history"] = (len(extras), sum(extras))
    return report


def history_matches(passwords, repo):
    """Count commits, across all branches, whose files contain a password.

    The patterns go to git in a private temporary file, never on a command line.
    """
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".patterns") as handle:
        os.chmod(handle.name, 0o600)
        handle.write("\n".join(sorted(passwords)) + "\n")
    try:
        revisions = subprocess.run(["git", "-C", str(repo), "rev-list", "--all"],
                                   capture_output=True, text=True, check=True).stdout.split()
        if not revisions:
            return 0, 0
        grep = subprocess.run(["git", "-C", str(repo), "grep", "-l", "-F", "-f", handle.name, *revisions],
                              capture_output=True, text=True, check=False)
        return len(revisions), len({line.split(":", 1)[0] for line in grep.stdout.splitlines()})
    finally:
        os.unlink(handle.name)


def _log_files():
    """The server log, wherever this install puts it, and the shell and psql history files."""
    logs = list(pathlib.Path("/opt/homebrew/var/log").glob("*postgres*"))
    logs += list(pathlib.Path("/usr/local/var/log").glob("*postgres*"))
    home = pathlib.Path.home()
    return logs + [home / name for name in (".psql_history", ".zsh_history", ".bash_history")]


def main():
    """Scan for the real credentials and exit non-zero if any leaked."""
    env_path = MODULE_DIR / ".env"
    if not env_path.exists():
        print("No .env, so there are no credentials to look for.")
        return 0
    passwords = credentials(env_path)
    if not passwords:
        print("The passwords in .env are placeholders; nothing to look for.")
        return 0
    report = scan(passwords, [MODULE_DIR], _log_files())
    commits, leaked_commits = history_matches(passwords, REPO_DIR)
    report["git history"] = (commits, leaked_commits)
    bad = 0
    print(f"Credential leak check: {len(passwords)} password(s) from .env")
    for label, (scanned, matched) in report.items():
        print(f"  {'ok  ' if matched == 0 else 'LEAK'} {label}: scanned {scanned}, matched {matched}")
        bad += matched
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
