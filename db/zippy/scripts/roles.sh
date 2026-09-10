#!/usr/bin/env bash
set -euo pipefail

mode=${1:-}

fail() {
    printf 'ERROR: %s\n' "$*" >&2
    exit 1
}

[[ "$mode" == bootstrap || "$mode" == teardown ]] || fail "usage: $0 {bootstrap|teardown}"
[[ "${ZIPPY_ALLOW_DISPOSABLE_DB:-}" == YES ]] || fail "ZIPPY_ALLOW_DISPOSABLE_DB=YES is required"
[[ -n "${PGDATABASE:-}" ]] || fail "PGDATABASE is required"
[[ "$PGDATABASE" != postgres && "$PGDATABASE" != template0 && "$PGDATABASE" != template1 ]] || fail "protected database rejected"
[[ "$PGDATABASE" =~ ^zippy_m2_disposable_[a-z0-9_]+$ ]] || fail "database name must identify an M2 disposable database"
[[ "${ZIPPY_CONFIRM_DISPOSABLE_DATABASE:-}" == "$PGDATABASE" ]] || fail "ZIPPY_CONFIRM_DISPOSABLE_DATABASE must equal PGDATABASE"
[[ -n "${ZIPPY_DISPOSABLE_MARKER:-}" ]] || fail "ZIPPY_DISPOSABLE_MARKER is required"
[[ -n "${ZIPPY_EXPECTED_CONTAINER:-}" ]] || fail "ZIPPY_EXPECTED_CONTAINER is required"
[[ -n "${ZIPPY_EXPECTED_VOLUME:-}" ]] || fail "ZIPPY_EXPECTED_VOLUME is required"
[[ -n "${ZIPPY_EXPECTED_IMAGE_DIGEST:-}" ]] || fail "ZIPPY_EXPECTED_IMAGE_DIGEST is required"
command -v psql >/dev/null || fail "psql is required"

psql_base=(psql -X --set=ON_ERROR_STOP=1 --no-psqlrc --quiet)
marker_row=$(${psql_base[@]} --tuples-only --no-align --field-separator=$'\t' --command="
    SELECT current_database(),
           current_setting('zippy.m2_marker', true),
           current_setting('zippy.m2_container', true),
           current_setting('zippy.m2_volume', true),
           current_setting('zippy.m2_image_digest', true),
           (SELECT rolsuper FROM pg_roles WHERE rolname = current_user)
")
IFS=$'\t' read -r actual_database actual_marker actual_container actual_volume actual_image is_superuser <<<"$marker_row"
[[ "$actual_database" == "$PGDATABASE" ]] || fail "current database does not match PGDATABASE"
[[ "$actual_marker" == "$ZIPPY_DISPOSABLE_MARKER" ]] || fail "disposable environment marker mismatch"
[[ "$actual_container" == "$ZIPPY_EXPECTED_CONTAINER" ]] || fail "container marker mismatch"
[[ "$actual_volume" == "$ZIPPY_EXPECTED_VOLUME" ]] || fail "volume marker mismatch"
[[ "$actual_image" == "$ZIPPY_EXPECTED_IMAGE_DIGEST" ]] || fail "image marker mismatch"
[[ "$is_superuser" == t ]] || fail "cluster-role management requires the disposable superuser"

unexpected_databases=$(${psql_base[@]} --tuples-only --no-align --command="
    SELECT string_agg(datname, ',' ORDER BY datname)
      FROM pg_database
     WHERE datallowconn
             AND datname NOT IN ('postgres', 'template0', 'template1', current_database())
")
[[ -z "$unexpected_databases" ]] || fail "unexpected connectable databases present: $unexpected_databases"

group_roles=(zippy_migrator zippy_app zippy_readonly)
login_roles=(zippy_m2_migration_login zippy_m2_app_login zippy_m2_readonly_login)

if [[ "$mode" == bootstrap ]]; then
    [[ -n "${ZIPPY_M2_MIGRATION_PASSWORD:-}" ]] || fail "ZIPPY_M2_MIGRATION_PASSWORD is required"
    [[ -n "${ZIPPY_M2_APP_PASSWORD:-}" ]] || fail "ZIPPY_M2_APP_PASSWORD is required"
    [[ -n "${ZIPPY_M2_READONLY_PASSWORD:-}" ]] || fail "ZIPPY_M2_READONLY_PASSWORD is required"
    existing=$(${psql_base[@]} --tuples-only --no-align --command="
        SELECT string_agg(rolname, ',' ORDER BY rolname)
          FROM pg_roles
         WHERE rolname IN (
             'zippy_migrator', 'zippy_app', 'zippy_readonly',
             'zippy_m2_migration_login', 'zippy_m2_app_login', 'zippy_m2_readonly_login'
         )
    ")
    [[ -z "$existing" ]] || fail "refusing to reuse existing roles: $existing"

    ${psql_base[@]} \
        --set=migration_password="$ZIPPY_M2_MIGRATION_PASSWORD" \
        --set=app_password="$ZIPPY_M2_APP_PASSWORD" \
        --set=readonly_password="$ZIPPY_M2_READONLY_PASSWORD" \
        --set=database_name="$PGDATABASE" <<'SQL'
CREATE ROLE zippy_migrator NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
CREATE ROLE zippy_app NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
CREATE ROLE zippy_readonly NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
CREATE ROLE zippy_m2_migration_login LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE INHERIT NOBYPASSRLS PASSWORD :'migration_password';
CREATE ROLE zippy_m2_app_login LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE INHERIT NOBYPASSRLS PASSWORD :'app_password';
CREATE ROLE zippy_m2_readonly_login LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE INHERIT NOBYPASSRLS PASSWORD :'readonly_password';
GRANT zippy_migrator TO zippy_m2_migration_login;
GRANT zippy_app TO zippy_m2_app_login;
GRANT zippy_readonly TO zippy_m2_readonly_login;
REVOKE ALL ON DATABASE :"database_name" FROM PUBLIC;
GRANT CONNECT, CREATE, TEMPORARY ON DATABASE :"database_name" TO zippy_migrator;
GRANT CONNECT, TEMPORARY ON DATABASE :"database_name" TO zippy_app, zippy_readonly;
SQL
    printf 'Disposable cluster roles bootstrapped.\n'
    exit 0
fi

[[ "${ZIPPY_CONFIRM_DISPOSABLE_ROLE_TEARDOWN:-}" == "$PGDATABASE:$ZIPPY_EXPECTED_CONTAINER:$ZIPPY_EXPECTED_VOLUME" ]] \
    || fail "ZIPPY_CONFIRM_DISPOSABLE_ROLE_TEARDOWN must confirm database, container, and volume"

schema_count=$(${psql_base[@]} --tuples-only --no-align --command="SELECT count(*) FROM pg_namespace WHERE nspname = 'zippy'")
[[ "$schema_count" == 0 ]] || fail "zippy schema must be removed before role teardown"

actual_roles=$(${psql_base[@]} --tuples-only --no-align --command="
    SELECT string_agg(rolname, ',' ORDER BY rolname)
      FROM pg_roles
     WHERE rolname LIKE 'zippy_%'
")
[[ "$actual_roles" == 'zippy_app,zippy_m2_app_login,zippy_m2_migration_login,zippy_m2_readonly_login,zippy_m2_runner,zippy_migrator,zippy_readonly' ]] \
    || fail "unexpected Zippy role set: $actual_roles"

${psql_base[@]} --set=database_name="$PGDATABASE" <<'SQL'
REVOKE CONNECT, CREATE, TEMPORARY ON DATABASE :"database_name" FROM zippy_migrator;
REVOKE CONNECT, TEMPORARY ON DATABASE :"database_name" FROM zippy_app, zippy_readonly;
REVOKE zippy_migrator FROM zippy_m2_migration_login;
REVOKE zippy_app FROM zippy_m2_app_login;
REVOKE zippy_readonly FROM zippy_m2_readonly_login;
SQL

dependencies=$(${psql_base[@]} --tuples-only --no-align --command="
    SELECT string_agg(role_record.rolname || ':' || dependency.deptype::text, ',' ORDER BY role_record.rolname, dependency.deptype)
      FROM pg_shdepend dependency
      JOIN pg_roles role_record ON role_record.oid = dependency.refobjid
     WHERE role_record.rolname IN (
         'zippy_migrator', 'zippy_app', 'zippy_readonly',
         'zippy_m2_migration_login', 'zippy_m2_app_login', 'zippy_m2_readonly_login'
     )
")
[[ -z "$dependencies" ]] || fail "role dependencies remain: $dependencies"

${psql_base[@]} <<'SQL'
DROP ROLE zippy_m2_migration_login;
DROP ROLE zippy_m2_app_login;
DROP ROLE zippy_m2_readonly_login;
DROP ROLE zippy_migrator;
DROP ROLE zippy_app;
DROP ROLE zippy_readonly;
SQL
printf 'Disposable cluster roles removed.\n'