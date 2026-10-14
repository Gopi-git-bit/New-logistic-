#!/usr/bin/env bash
set -euo pipefail
[[ ${1:-} == bootstrap || ${1:-} == teardown ]] || exit 2
[[ ${PAPERCLIP_ALLOW_DISPOSABLE_DB:-} == YES && ${PGDATABASE:-} =~ ^paperclip_m5_disposable_ ]] || exit 2
if [[ $1 == bootstrap ]]; then
  psql -X --set=ON_ERROR_STOP=1 --no-psqlrc <<'SQL'
CREATE ROLE paperclip_migrator NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
CREATE ROLE paperclip_function_owner NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
CREATE ROLE paperclip_app NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
CREATE ROLE paperclip_m5_migration_login LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE INHERIT NOBYPASSRLS;
CREATE ROLE paperclip_m5_app_login LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE INHERIT NOBYPASSRLS;
GRANT paperclip_migrator TO paperclip_m5_migration_login; GRANT paperclip_app TO paperclip_m5_app_login;
-- Migrator may only SET ROLE to transfer function ownership; it never inherits the owner's privileges.
GRANT paperclip_function_owner TO paperclip_migrator WITH INHERIT FALSE, SET TRUE;
REVOKE ALL ON SCHEMA public FROM PUBLIC;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
GRANT USAGE ON SCHEMA public TO paperclip_migrator;
-- SECURITY DEFINER functions resolve public.digest as the function owner; USAGE only, never CREATE.
GRANT USAGE ON SCHEMA public TO paperclip_function_owner;
GRANT EXECUTE ON FUNCTION public.digest(text, text) TO paperclip_migrator;
GRANT EXECUTE ON FUNCTION public.digest(bytea, text) TO paperclip_migrator;
GRANT EXECUTE ON FUNCTION public.digest(text, text) TO paperclip_function_owner;
GRANT EXECUTE ON FUNCTION public.digest(bytea, text) TO paperclip_function_owner;
SELECT format('REVOKE ALL ON DATABASE %I FROM PUBLIC', current_database()) \gexec
SELECT format('GRANT CONNECT, TEMPORARY ON DATABASE %I TO paperclip_app', current_database()) \gexec
SELECT format('GRANT CONNECT, CREATE ON DATABASE %I TO paperclip_migrator', current_database()) \gexec
SQL
else
  psql -X --set=ON_ERROR_STOP=1 --no-psqlrc -c 'DROP ROLE IF EXISTS paperclip_m5_app_login,paperclip_m5_migration_login,paperclip_app,paperclip_function_owner,paperclip_migrator;'
fi