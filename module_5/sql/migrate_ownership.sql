-- migrate_ownership.sql: move an existing applicants table under the owner account.
--
-- EN 605.256 Modern Software Concepts in Python, Module 5.
-- Joshua Latz (jlatz1)
--
-- For a database that already has the table, created by a superuser or by your
-- own account in Module 3 or 4. Run after roles.sql, connected to the database,
-- as a superuser, from module_5/:
--
--   psql -d gradcafedb -f sql/migrate_ownership.sql
--
-- Only the owner can CREATE or COMMENT on the table, which is what keeps the
-- runtime account from changing the schema. The data is not touched, and the
-- change is reversible: ALTER TABLE applicants OWNER TO <previous owner>.

\set ON_ERROR_STOP on

ALTER TABLE applicants OWNER TO gradcafe_owner;
\ir grants.sql
