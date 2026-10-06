-- grants.sql: give the runtime account the table privileges it needs, and no others.
--
-- EN 605.256 Modern Software Concepts in Python, Module 5.
-- Joshua Latz (jlatz1)
--
-- Run after the owner has created the table, connected to the database, as
-- gradcafe_owner or a superuser, from module_5/:
--
--   psql -d gradcafedb -f sql/grants.sql
--
-- SELECT serves the analysis page, GET /api/applicants, and the pull's read of
-- the newest entry. INSERT serves Pull Data; ON CONFLICT DO NOTHING needs no
-- UPDATE. There is no UPDATE, DELETE, TRUNCATE, REFERENCES, or TRIGGER, no
-- sequence grant (p_id is not serial), and no ALTER DEFAULT PRIVILEGES, so a
-- future table starts with nothing granted.
--
-- Safe to run again: it first strips every privilege, so a grant added by hand
-- is removed rather than left behind.

\set ON_ERROR_STOP on

REVOKE ALL ON applicants FROM PUBLIC;
REVOKE ALL ON applicants FROM gradcafe_app;
GRANT SELECT, INSERT ON applicants TO gradcafe_app;
