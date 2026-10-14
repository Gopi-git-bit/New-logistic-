#!/usr/bin/env bash
set -euo pipefail

mode=${1:-}
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
migration_dir=$(cd -- "$script_dir/../migrations" && pwd)
manifest="$migration_dir/manifest.tsv"

fail() {
    printf 'ERROR: %s\n' "$*" >&2
    exit 1
}

[[ "$mode" == up || "$mode" == down || "$mode" == verify ]] || fail "usage: $0 {up|down|verify}"
[[ -n "${PGDATABASE:-}" ]] || fail "PGDATABASE is required"
[[ "$PGDATABASE" != postgres && "$PGDATABASE" != template0 && "$PGDATABASE" != template1 ]] || fail "protected database rejected"
[[ "$PGDATABASE" =~ ^zippy_m2_disposable_[a-z0-9_]+$ ]] || fail "database name must identify an M2 disposable database"
[[ "${ZIPPY_ALLOW_DISPOSABLE_DB:-}" == YES ]] || fail "ZIPPY_ALLOW_DISPOSABLE_DB=YES is required"
[[ "${ZIPPY_CONFIRM_DISPOSABLE_DATABASE:-}" == "$PGDATABASE" ]] || fail "ZIPPY_CONFIRM_DISPOSABLE_DATABASE must equal PGDATABASE"
[[ -n "${ZIPPY_DISPOSABLE_MARKER:-}" ]] || fail "ZIPPY_DISPOSABLE_MARKER is required"
[[ -n "${ZIPPY_EXPECTED_CONTAINER:-}" ]] || fail "ZIPPY_EXPECTED_CONTAINER is required"
[[ -n "${ZIPPY_EXPECTED_VOLUME:-}" ]] || fail "ZIPPY_EXPECTED_VOLUME is required"
[[ -n "${ZIPPY_EXPECTED_IMAGE_DIGEST:-}" ]] || fail "ZIPPY_EXPECTED_IMAGE_DIGEST is required"
command -v psql >/dev/null || fail "psql is required"
command -v sha256sum >/dev/null || fail "sha256sum is required"

mapfile -t rows < <(tail -n +2 "$manifest")
[[ ${#rows[@]} -gt 0 ]] || fail "manifest is empty"

declare -A approved_files=()
previous_version=''
for row in "${rows[@]}"; do
    IFS=$'\t' read -r version up_file up_sha down_file down_sha rollback_class <<<"$row"
    [[ -n "$version" && "$version" > "$previous_version" ]] || fail "manifest versions are not strictly ordered"
    [[ "$rollback_class" == disposable_only ]] || fail "unsupported rollback class for $version"
    for pair in "$up_file:$up_sha" "$down_file:$down_sha"; do
        file=${pair%%:*}
        expected_sha=${pair#*:}
        [[ "$file" != */* && "$file" == *.sql ]] || fail "invalid manifest path: $file"
        [[ -f "$migration_dir/$file" ]] || fail "missing migration: $file"
        actual_sha=$(sha256sum "$migration_dir/$file" | awk '{print $1}')
        [[ "$actual_sha" == "$expected_sha" ]] || fail "checksum drift: $file"
        approved_files["$file"]=1
    done
    previous_version=$version
done

while IFS= read -r sql_path; do
    sql_file=${sql_path##*/}
    [[ -n "${approved_files[$sql_file]:-}" ]] || fail "non-manifest migration rejected: $sql_file"
done < <(find "$migration_dir" -maxdepth 1 -type f -name '*.sql' -print | LC_ALL=C sort)

psql_base=(psql -X --set=ON_ERROR_STOP=1 --no-psqlrc)

marker_row=$(${psql_base[@]} --tuples-only --no-align --field-separator=$'\t' --command="
    SELECT current_database(),
           current_setting('zippy.m2_marker', true),
           current_setting('zippy.m2_container', true),
           current_setting('zippy.m2_volume', true),
           current_setting('zippy.m2_image_digest', true)
")
IFS=$'\t' read -r actual_database actual_marker actual_container actual_volume actual_image <<<"$marker_row"
[[ "$actual_database" == "$PGDATABASE" ]] || fail "current database does not match PGDATABASE"
[[ "$actual_marker" == "$ZIPPY_DISPOSABLE_MARKER" ]] || fail "disposable environment marker mismatch"
[[ "$actual_container" == "$ZIPPY_EXPECTED_CONTAINER" ]] || fail "container marker mismatch"
[[ "$actual_volume" == "$ZIPPY_EXPECTED_VOLUME" ]] || fail "volume marker mismatch"
[[ "$actual_image" == "$ZIPPY_EXPECTED_IMAGE_DIGEST" ]] || fail "image marker mismatch"

if [[ "$mode" == verify ]]; then
    applied=$(${psql_base[@]} --tuples-only --no-align --command="SELECT version || E'\\t' || checksum_sha256 FROM zippy.schema_migrations ORDER BY version")
    expected=$(printf '%s\n' "${rows[@]}" | awk -F'\t' '{print $1 "\t" $3}')
    [[ "$applied" == "$expected" ]] || fail "migration ledger differs from manifest"
    printf 'Canonical migration ledger verified.\n'
    exit 0
fi

if [[ "$mode" == up ]]; then
    for row in "${rows[@]}"; do
        IFS=$'\t' read -r version up_file up_sha _ <<<"$row"
        if [[ "$version" != 0001_foundation ]] && ! ${psql_base[@]} --tuples-only --no-align --command="SELECT 1 FROM zippy.schema_migrations WHERE version = '$previous_applied'" | grep -qx 1; then
            fail "prior migration is not applied: $previous_applied"
        fi
        if ${psql_base[@]} --tuples-only --no-align --command="SELECT to_regclass('zippy.schema_migrations') IS NOT NULL" | grep -qx t; then
            existing=$(${psql_base[@]} --tuples-only --no-align --command="SELECT checksum_sha256 FROM zippy.schema_migrations WHERE version = '$version'")
            if [[ -n "$existing" ]]; then
                [[ "$existing" == "$up_sha" ]] || fail "applied checksum drift: $version"
                previous_applied=$version
                continue
            fi
        fi
        ${psql_base[@]} --file="$migration_dir/$up_file"
        ${psql_base[@]} --command="INSERT INTO zippy.schema_migrations(version, checksum_sha256) VALUES ('$version', '$up_sha')"
        previous_applied=$version
    done
    "$0" verify
    exit 0
fi

[[ "${ZIPPY_CONFIRM_DISPOSABLE_DOWN:-}" == "$PGDATABASE" ]] || fail "ZIPPY_CONFIRM_DISPOSABLE_DOWN must equal PGDATABASE"
"$0" verify
unexpected_schemas=$(${psql_base[@]} --tuples-only --no-align --command="
        SELECT string_agg(nspname, ',' ORDER BY nspname)
            FROM pg_namespace
         WHERE nspname !~ '^pg_'
             AND nspname NOT IN ('information_schema', 'public', 'zippy')
")
[[ -z "$unexpected_schemas" ]] || fail "unexpected user schemas present: $unexpected_schemas"
unexpected_databases=$(${psql_base[@]} --tuples-only --no-align --command="
        SELECT string_agg(datname, ',' ORDER BY datname)
            FROM pg_database
         WHERE datallowconn
                 AND datname NOT IN ('postgres', 'template0', 'template1', current_database())
")
[[ -z "$unexpected_databases" ]] || fail "unexpected connectable databases present: $unexpected_databases"
for ((index=${#rows[@]}-1; index>=0; index--)); do
    IFS=$'\t' read -r version _ _ down_file _ _ <<<"${rows[$index]}"
    ${psql_base[@]} --file="$migration_dir/$down_file"
    if [[ "$version" != 0001_foundation ]]; then
        ${psql_base[@]} --command="DELETE FROM zippy.schema_migrations WHERE version = '$version'"
    fi
done
printf 'Canonical migrations rolled back from disposable database.\n'