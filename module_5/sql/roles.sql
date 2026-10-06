-- roles.sql: create the two database accounts and lock the database to them.
--
-- EN 605.256 Modern Software Concepts in Python, Module 5.
-- Joshua Latz (jlatz1)
--
-- Run once per database, as a PostgreSQL superuser, from module_5/. The
-- passwords are never given to psql or to the server. Each is turned into a
-- SCRAM-SHA-256 verifier first and handed over in the environment, so it is
-- not on a command line (visible in the process list) and not in the text of
-- any statement (written to the server log if the statement fails):
--
--   export OWNER_VERIFIER=$(printf %s "$OWNER_PW" | python3 scripts/scram_verifier.py)
--   export APP_VERIFIER=$(printf %s "$APP_PW" | python3 scripts/scram_verifier.py)
--   psql -d postgres -v db=gradcafedb -f sql/roles.sql
--
-- Two accounts (decision D1 in PLAN.md). gradcafe_owner owns the table and does
-- schema setup and the bulk load. gradcafe_app is what the running web app and
-- Pull Data connect as, so a flaw in either can do no more than read and add
-- applicant rows. Neither is a superuser, and neither can create databases or
-- roles. grants.sql, run after the owner has created the table, gives the app
-- role its table privileges.
--
-- Safe to run again: roles that exist are updated, not recreated, which is how
-- a password is rotated. Roles are cluster-wide; the grants below are for the
-- database named by :db.

\set ON_ERROR_STOP on

\getenv owner_verifier OWNER_VERIFIER
\getenv app_verifier APP_VERIFIER

SELECT 'CREATE ROLE gradcafe_owner LOGIN'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'gradcafe_owner') \gexec
SELECT 'CREATE ROLE gradcafe_app LOGIN'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'gradcafe_app') \gexec

ALTER ROLE gradcafe_owner WITH LOGIN PASSWORD :'owner_verifier'
    NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
ALTER ROLE gradcafe_app WITH LOGIN PASSWORD :'app_verifier'
    NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS CONNECTION LIMIT 20;

-- Only these two accounts, and superusers, may connect to the database.
REVOKE ALL ON DATABASE :"db" FROM PUBLIC;
GRANT CONNECT ON DATABASE :"db" TO gradcafe_owner, gradcafe_app;

-- Schema privileges belong to the database, so connect to it first.
\connect :"db"

REVOKE CREATE ON SCHEMA public FROM PUBLIC;     -- the default since PostgreSQL 15, explicit for older servers
GRANT USAGE, CREATE ON SCHEMA public TO gradcafe_owner;
GRANT USAGE ON SCHEMA public TO gradcafe_app;
