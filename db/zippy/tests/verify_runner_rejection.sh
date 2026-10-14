#!/usr/bin/env bash
set -euo pipefail

source_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
temp_root=$(mktemp -d)
trap 'rm -rf "$temp_root"' EXIT

mkdir -p "$temp_root/scripts" "$temp_root/migrations"
cp "$source_root/scripts/migrate.sh" "$temp_root/scripts/migrate.sh"
cp "$source_root/migrations/"* "$temp_root/migrations/"

expect_failure() {
    local label=$1
    local expected_error=$2
    shift 2
    if "$@" 2>"$temp_root/error.log"; then
        printf 'runner accepted rejected case: %s\n' "$label" >&2
        exit 1
    fi
    grep -Fq "$expected_error" "$temp_root/error.log" || {
        printf 'runner returned wrong error for %s\n' "$label" >&2
        cat "$temp_root/error.log" >&2
        exit 1
    }
}

expect_failure missing_opt_in 'ZIPPY_ALLOW_DISPOSABLE_DB=YES is required' \
    env -u ZIPPY_ALLOW_DISPOSABLE_DB "$source_root/scripts/migrate.sh" verify
expect_failure incorrect_confirmation 'ZIPPY_CONFIRM_DISPOSABLE_DOWN must equal PGDATABASE' \
    env ZIPPY_CONFIRM_DISPOSABLE_DOWN=wrong "$source_root/scripts/migrate.sh" down
expect_failure protected_database 'protected database rejected' \
    env PGDATABASE=postgres ZIPPY_CONFIRM_DISPOSABLE_DATABASE=postgres "$source_root/scripts/migrate.sh" verify
expect_failure absent_marker 'ZIPPY_DISPOSABLE_MARKER is required' \
    env -u ZIPPY_DISPOSABLE_MARKER "$source_root/scripts/migrate.sh" verify
expect_failure incorrect_marker 'disposable environment marker mismatch' \
    env ZIPPY_DISPOSABLE_MARKER=incorrect "$source_root/scripts/migrate.sh" verify

original_up_sha=$(awk -F'\t' 'NR == 2 {print $3}' "$temp_root/migrations/manifest.tsv")
sed -i "2s/$original_up_sha/$(printf '0%.0s' {1..64})/" "$temp_root/migrations/manifest.tsv"
expect_failure unexpected_checksum 'checksum drift:' "$temp_root/scripts/migrate.sh" verify
cp "$source_root/migrations/manifest.tsv" "$temp_root/migrations/manifest.tsv"

printf '%s\n' 'SELECT 1;' > "$temp_root/migrations/9999_unexpected.sql"
expect_failure unexpected_file 'non-manifest migration rejected: 9999_unexpected.sql' \
    "$temp_root/scripts/migrate.sh" verify

if grep -RInE '\bDROP[[:space:]]+ROLE\b' "$source_root/migrations" "$source_root/scripts/migrate.sh"; then
    printf 'normal migration path contains role teardown\n' >&2
    exit 1
fi

printf 'Runner rejected missing opt-in, incorrect confirmation, protected database, absent/incorrect marker, checksum drift, unexpected SQL, and normal-down role teardown.\n'