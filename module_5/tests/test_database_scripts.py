"""The database setup scripts never carry, send, or log a cleartext password (CHG-12).

EN 605.256 Modern Software Concepts in Python, Module 5.
Joshua Latz (jlatz1)

A password can leak by four routes besides a committed file: the process list
(an argument to psql), the server log (the text of a statement that failed),
shell and psql history, and documentation that tells a reader to do any of
those. The design closes all four: roles.sql takes SCRAM-SHA-256 verifiers from
the environment, and scripts/scram_verifier.py makes them from a password read
on standard input. These tests pin that design, and the live setup was checked
for leaks directly (see "Credentials were checked for leaks" in the README).
"""

import base64
import hashlib
import hmac
import importlib.util
import re
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.security

MODULE_DIR = Path(__file__).resolve().parent.parent
SQL_DIR = MODULE_DIR / "sql"
SCRIPT = MODULE_DIR / "scripts" / "scram_verifier.py"
SETUP_SCRIPTS = ("roles.sql", "grants.sql", "migrate_ownership.sql")
VERIFIER = re.compile(r"SCRAM-SHA-256\$(\d+):([A-Za-z0-9+/=]+)\$([A-Za-z0-9+/=]+):([A-Za-z0-9+/=]+)")


@pytest.fixture(scope="module")
def scram():
    spec = importlib.util.spec_from_file_location("scram_verifier", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# --- the verifier -----------------------------------------------------------

def test_verifier_has_the_format_postgresql_stores(scram):
    match = VERIFIER.fullmatch(scram.scram_verifier("a-password"))
    assert match and int(match.group(1)) == 4096
    assert len(base64.b64decode(match.group(2))) == 16          # the salt
    assert len(base64.b64decode(match.group(3))) == 32          # StoredKey, a SHA-256 digest
    assert len(base64.b64decode(match.group(4))) == 32          # ServerKey


def test_verifier_matches_an_independent_computation_from_rfc_5802(scram):
    """Recompute StoredKey and ServerKey from the password and the salt in the verifier."""
    password, salt = "correct horse", bytes(range(16))
    verifier = scram.scram_verifier(password, salt=salt, iterations=4096)
    _, encoded_salt, stored, server = VERIFIER.fullmatch(verifier).groups()[0:4]
    assert base64.b64decode(encoded_salt) == salt

    salted = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 4096)
    client_key = hmac.digest(salted, b"Client Key", "sha256")
    assert base64.b64decode(stored) == hashlib.sha256(client_key).digest()
    assert base64.b64decode(server) == hmac.digest(salted, b"Server Key", "sha256")


def test_verifier_is_salted_so_the_same_password_gives_different_verifiers(scram):
    assert scram.scram_verifier("same") != scram.scram_verifier("same")


def test_verifier_with_a_fixed_salt_is_deterministic_and_password_specific(scram):
    salt = b"0123456789abcdef"
    assert scram.scram_verifier("a", salt=salt) == scram.scram_verifier("a", salt=salt)
    assert scram.scram_verifier("a", salt=salt) != scram.scram_verifier("b", salt=salt)


def test_the_verifier_does_not_contain_the_password(scram):
    password = "very-recognizable-secret-9187"
    assert password not in scram.scram_verifier(password)
    assert base64.b64encode(password.encode()).decode() not in scram.scram_verifier(password)


@pytest.mark.parametrize("bad", ["", "pässword", "密码"])
def test_verifier_refuses_empty_and_non_ascii_passwords(scram, bad):
    """SASLprep is not implemented, and a role nobody can log in as is worse than an error."""
    with pytest.raises(ValueError, match="non-empty ASCII"):
        scram.scram_verifier(bad)


def test_the_command_reads_stdin_and_prints_only_the_verifier():
    password = "a-throwaway-password-4417"
    result = subprocess.run([sys.executable, str(SCRIPT)], input=password + "\n",
                            capture_output=True, text=True, check=True)
    assert VERIFIER.fullmatch(result.stdout.strip())
    assert password not in result.stdout and password not in result.stderr


def test_the_command_takes_no_password_argument():
    """An argument would be visible in the process list, so the script must not read one."""
    password = "argument-password-5521"
    result = subprocess.run([sys.executable, str(SCRIPT), password], input="stdin-password\n",
                            capture_output=True, text=True, check=True)
    assert VERIFIER.fullmatch(result.stdout.strip())
    assert password not in result.stdout


# --- the scripts ------------------------------------------------------------

@pytest.mark.parametrize("name", SETUP_SCRIPTS)
def test_setup_scripts_contain_no_password_literal(name):
    text = (SQL_DIR / name).read_text(encoding="utf-8")
    assert not re.search(r"(?i)\bpassword\s+'", text)


def test_roles_sql_takes_verifiers_from_the_environment_not_passwords():
    text = (SQL_DIR / "roles.sql").read_text(encoding="utf-8")
    assert r"\getenv owner_verifier OWNER_VERIFIER" in text
    assert r"\getenv app_verifier APP_VERIFIER" in text
    assert "PASSWORD :'owner_verifier'" in text and "PASSWORD :'app_verifier'" in text
    assert "owner_pw" not in text and "app_pw" not in text


@pytest.mark.parametrize("name", SETUP_SCRIPTS)
def test_setup_scripts_stop_on_the_first_error(name):
    assert r"\set ON_ERROR_STOP on" in (SQL_DIR / name).read_text(encoding="utf-8")


def test_the_documented_setup_never_passes_a_cleartext_password_to_psql():
    readme = (MODULE_DIR / "README.md").read_text(encoding="utf-8")
    # The instructions only: the next section names the bad practice on purpose, as the example to avoid.
    setup = readme[readme.index("### Database setup"):readme.index("### Credentials were checked for leaks")]
    assert "scram_verifier.py" in setup
    assert "owner_pw" not in setup and "app_pw" not in setup
    assert not re.search(r"psql[^\n]*-v\s+\w*(pw|pass)", setup, re.IGNORECASE)


def test_nothing_in_sql_is_ignored_by_the_secrets_scan():
    """sql/ is scanned by scripts/check_secrets.py, so a password literal there fails the gate."""
    spec = importlib.util.spec_from_file_location("check_secrets", MODULE_DIR / "scripts" / "check_secrets.py")
    secrets = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(secrets)
    assert "sql" in secrets.SCAN_DIRS and ".sql" in secrets.SCAN_SUFFIXES
