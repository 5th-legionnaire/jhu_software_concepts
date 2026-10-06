"""scram_verifier.py: turn a password into the SCRAM-SHA-256 verifier PostgreSQL stores.

EN 605.256 Modern Software Concepts in Python, Module 5.
Joshua Latz (jlatz1)

sql/roles.sql sets each role's password from a verifier, never from the
password. PostgreSQL accepts a SCRAM verifier in place of a password and stores
it unchanged, so the cleartext password never reaches the server. That matters
because the server writes the text of a statement that fails to its log
(log_min_error_statement), and a log is often readable by every local user. An
ALTER ROLE that carried a password and failed would put the password in it; one
that carries a verifier puts a salted hash there.

The verifier is the one RFC 5802 defines, in the format PostgreSQL documents:
    SCRAM-SHA-256$<iterations>:<salt>$<StoredKey>:<ServerKey>

Contains:
    scram_verifier():  the verifier for a password
    main():            read a password on standard input, print its verifier

Usage (the password is read from standard input, so it is never an argument):
    printf %s "$APP_PW" | python3 scripts/scram_verifier.py
"""

import base64
import hashlib
import hmac
import os
import sys

ITERATIONS = 4096  # PostgreSQL's default scram_iterations


def scram_verifier(password, salt=None, iterations=ITERATIONS):
    """Return the SCRAM-SHA-256 verifier for a password.

    Args:
        password: the cleartext password. ASCII only: PostgreSQL normalizes
            other text with SASLprep, which this function does not implement,
            and a mismatch would leave a role nobody can log in as.
        salt: 16 random bytes by default; fixed only by tests.
        iterations: the PBKDF2 iteration count.

    Returns:
        str: the verifier, safe to log or store.

    Raises:
        ValueError: if the password is not ASCII or is empty.
    """
    if not password or not password.isascii():
        raise ValueError("the password must be a non-empty ASCII string")
    salt = os.urandom(16) if salt is None else salt
    salted = hashlib.pbkdf2_hmac("sha256", password.encode("ascii"), salt, iterations)
    client_key = hmac.new(salted, b"Client Key", hashlib.sha256).digest()
    stored_key = hashlib.sha256(client_key).digest()
    server_key = hmac.new(salted, b"Server Key", hashlib.sha256).digest()
    encode = lambda raw: base64.b64encode(raw).decode("ascii")  # noqa: E731
    return f"SCRAM-SHA-256${iterations}:{encode(salt)}${encode(stored_key)}:{encode(server_key)}"


def main():
    """Print the verifier for the password on standard input."""
    password = sys.stdin.read().rstrip("\r\n")
    print(scram_verifier(password))


if __name__ == "__main__":
    main()
