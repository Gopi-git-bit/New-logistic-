#!/usr/bin/env bash
set -euo pipefail

readonly image='postgres@sha256:f1c3376c26f2609ab9f29f71f824103fe2fcd8ee0346485cb6122a4f93df6f94'
readonly expected_image_id='sha256:f1c3376c26f2609ab9f29f71f824103fe2fcd8ee0346485cb6122a4f93df6f94'
readonly repository_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." && pwd)
readonly python_bin=${ZIPPY_M3_PYTHON:-/tmp/zippy-m3-venv/bin/python}
readonly suffix="$(date -u +%Y%m%d%H%M%S)_$(tr -d '-' </proc/sys/kernel/random/uuid | cut -c1-8)"
readonly container="zippy-m3-disposable-${suffix//_/-}"
readonly volume="zippy_m3_disposable_${suffix}_data"
readonly database="zippy_m2_disposable_${suffix}"
readonly socket_dir=$(mktemp -d "/tmp/zippy-m3-socket-${suffix}.XXXXXX")
readonly marker=$(cat /proc/sys/kernel/random/uuid)
readonly super_password="$(tr -d '-' </proc/sys/kernel/random/uuid)$(tr -d '-' </proc/sys/kernel/random/uuid)"
readonly migration_password="$(tr -d '-' </proc/sys/kernel/random/uuid)$(tr -d '-' </proc/sys/kernel/random/uuid)"
readonly app_password="$(tr -d '-' </proc/sys/kernel/random/uuid)$(tr -d '-' </proc/sys/kernel/random/uuid)"
readonly readonly_password="$(tr -d '-' </proc/sys/kernel/random/uuid)$(tr -d '-' </proc/sys/kernel/random/uuid)"

cleanup() {
    status=$?
    if [[ $status -ne 0 ]] && docker inspect "$container" >/dev/null 2>&1; then
        docker logs "$container" >&2 || true
    fi
    docker rm -f "$container" >/dev/null 2>&1 || true
    docker volume rm "$volume" >/dev/null 2>&1 || true
    rm -rf "$socket_dir"
    return "$status"
}
trap cleanup EXIT

[[ -x "$python_bin" ]]
[[ "$(docker image inspect "$image" --format '{{.Id}}')" == "$expected_image_id" ]]
[[ "$(ss -lntH | awk '{print $4}' | grep -Ec '(^|:)(5432)$' || true)" == 0 ]]
# Resolve the pinned image's postgres UID/GID, then restrict the private Unix
# socket directory to that identity (mode 0700). Host-side tests and docker
# exec run as root, which retains access without broadening permissions.
postgres_ids=$(docker run --rm --network none --entrypoint id "$image" postgres)
postgres_uid=$(printf '%s\n' "$postgres_ids" | sed -n 's/^uid=\([0-9][0-9]*\)(.*/\1/p')
postgres_gid=$(printf '%s\n' "$postgres_ids" | sed -n 's/.* gid=\([0-9][0-9]*\)(.*/\1/p')
[[ "$postgres_uid" =~ ^[0-9]+$ && "$postgres_gid" =~ ^[0-9]+$ ]]
chown "$postgres_uid:$postgres_gid" "$socket_dir"
chmod 0700 "$socket_dir"
docker volume create "$volume" >/dev/null
docker run -d \
    --name "$container" \
    --network none \
    --mount "type=volume,source=$volume,target=/var/lib/postgresql/data" \
    --mount "type=bind,source=$repository_root,target=/workspace,readonly" \
    --mount "type=bind,source=$socket_dir,target=/var/run/postgresql" \
    --health-cmd="pg_isready -h /var/run/postgresql -U zippy_m2_runner -d $database" \
    --health-interval=1s \
    --health-timeout=1s \
    --health-retries=60 \
    -e POSTGRES_USER=zippy_m2_runner \
    -e POSTGRES_PASSWORD="$super_password" \
    -e POSTGRES_INITDB_ARGS=--auth-local=scram-sha-256 \
    -e POSTGRES_DB="$database" \
    "$image" >/dev/null

ready=false
for _ in {1..120}; do
    ready_events=$(docker logs "$container" 2>&1 | grep -c 'database system is ready to accept connections' || true)
    if [[ "$ready_events" -ge 2 ]] \
       && docker exec "$container" pg_isready -h /var/run/postgresql -U zippy_m2_runner -d "$database" >/dev/null 2>&1; then
        ready=true
        break
    fi
    read -r -t 1 _ </dev/null || true
done
[[ "$ready" == true ]]
[[ "$(docker inspect -f '{{.HostConfig.NetworkMode}}' "$container")" == none ]]
[[ -z "$(docker port "$container")" ]]

# The image entrypoint broadens /var/run/postgresql during startup; restore the
# hardened mode after initialization and before any host-side access. Assert on
# the permission bits only: this filesystem preserves the harmless setgid bit
# through chmod, so %a may report 2700 rather than 700.
chmod 0700 "$socket_dir"
socket_dir_mode_hex=$(stat -c '%f' "$socket_dir")
(( (16#$socket_dir_mode_hex & 8#077) == 0 ))
[[ "$(stat -c '%u:%g' "$socket_dir")" == "$postgres_uid:$postgres_gid" ]]

# Record effective socket and authentication state for evidence.
socket_dir_mode=$(stat -c '%a' "$socket_dir")
socket_file_mode=$(stat -c '%a' "$socket_dir/.s.PGSQL.5432")
auth_record=$(docker exec -e PGHOST=/var/run/postgresql -e PGPASSWORD="$super_password" "$container" \
    psql -X --tuples-only --no-align --no-psqlrc -U zippy_m2_runner -d postgres \
    --field-separator=$'\t' --command="SELECT current_setting('password_encryption'), (SELECT string_agg(DISTINCT auth_method, ',' ORDER BY auth_method) FROM pg_hba_file_rules WHERE type = 'local')")
IFS=$'\t' read -r password_encryption pg_hba_local_auth <<<"$auth_record"
[[ "$password_encryption" == "scram-sha-256" ]]
[[ "$pg_hba_local_auth" == "scram-sha-256" ]]

common_env=(
    -e PGHOST=/var/run/postgresql
    -e PGDATABASE="$database"
    -e ZIPPY_ALLOW_DISPOSABLE_DB=YES
    -e ZIPPY_CONFIRM_DISPOSABLE_DATABASE="$database"
    -e ZIPPY_DISPOSABLE_MARKER="$marker"
    -e ZIPPY_EXPECTED_CONTAINER="$container"
    -e ZIPPY_EXPECTED_VOLUME="$volume"
    -e ZIPPY_EXPECTED_IMAGE_DIGEST="$image"
)

docker exec -i -e PGHOST=/var/run/postgresql -e PGPASSWORD="$super_password" "$container" \
    psql -X --set=ON_ERROR_STOP=1 --quiet -U zippy_m2_runner -d postgres \
    --set=database_name="$database" --set=marker="$marker" --set=container_name="$container" \
    --set=volume_name="$volume" --set=image_digest="$image" <<'SQL'
ALTER DATABASE :"database_name" SET "zippy.m2_marker" TO :'marker';
ALTER DATABASE :"database_name" SET "zippy.m2_container" TO :'container_name';
ALTER DATABASE :"database_name" SET "zippy.m2_volume" TO :'volume_name';
ALTER DATABASE :"database_name" SET "zippy.m2_image_digest" TO :'image_digest';
SQL

docker exec "${common_env[@]}" \
    -e PGUSER=zippy_m2_runner -e PGPASSWORD="$super_password" \
    -e ZIPPY_M2_MIGRATION_PASSWORD="$migration_password" \
    -e ZIPPY_M2_APP_PASSWORD="$app_password" \
    -e ZIPPY_M2_READONLY_PASSWORD="$readonly_password" \
    "$container" /workspace/db/zippy/scripts/roles.sh bootstrap

run_migrator() {
    docker exec "${common_env[@]}" \
        -e PGUSER=zippy_m2_migration_login -e PGPASSWORD="$migration_password" \
        -e PGOPTIONS='-c role=zippy_migrator' "$container" "$@"
}

run_migrator /workspace/db/zippy/scripts/migrate.sh up
docker exec "${common_env[@]}" -e PGUSER=zippy_m2_runner -e PGPASSWORD="$super_password" "$container" \
    psql -X --set=ON_ERROR_STOP=1 --quiet --no-psqlrc --file=/workspace/db/zippy/tests/setup_m3.sql

# Negative check: an unrelated non-root host identity must not reach the
# hardened socket directory. Safely skipped (NOT VERIFIED) without root or
# setpriv; no host accounts are created or modified.
negative_local_user='NOT VERIFIED'
if [[ "$(id -u)" == 0 ]] && command -v setpriv >/dev/null 2>&1; then
    negative_rc=0
    ZIPPY_M3_TEST_DATABASE_URL="host=$socket_dir dbname=$database user=zippy_m2_app_login" \
        setpriv --reuid=65534 --regid=65534 --clear-groups "$python_bin" - <<'PY' || negative_rc=$?
import os
import sys

import psycopg

try:
    psycopg.connect(os.environ["ZIPPY_M3_TEST_DATABASE_URL"], connect_timeout=3)
except psycopg.OperationalError as exc:
    message = str(exc)
    denied = (
        "ermission denied" in message
        or "password authentication failed" in message
        or "no password supplied" in message
    )
    if denied:
        sys.exit(0)
    print(f"unexpected connection failure: {type(exc).__name__}", file=sys.stderr)
    sys.exit(3)
sys.exit(1)
PY
    case "$negative_rc" in
        0) negative_local_user='PASS' ;;
        1)
            printf 'ERROR: unrelated non-root identity connected to the disposable socket\n' >&2
            exit 1
            ;;
        *) negative_local_user='NOT VERIFIED' ;;
    esac
fi

ZIPPY_M3_TEST_DATABASE_URL="host=$socket_dir dbname=$database user=zippy_m2_app_login password=$app_password" \
PYTHONPATH="$repository_root" \
    "$python_bin" -m pytest "$repository_root/api/tests" -q

run_migrator env ZIPPY_CONFIRM_DISPOSABLE_DOWN="$database" /workspace/db/zippy/scripts/migrate.sh down
docker exec "${common_env[@]}" \
    -e PGUSER=zippy_m2_runner -e PGPASSWORD="$super_password" \
    -e ZIPPY_CONFIRM_DISPOSABLE_ROLE_TEARDOWN="$database:$container:$volume" \
    "$container" /workspace/db/zippy/scripts/roles.sh teardown

version=$(docker exec "${common_env[@]}" -e PGUSER=zippy_m2_runner -e PGPASSWORD="$super_password" "$container" \
    psql -X --tuples-only --no-align --no-psqlrc --command='SHOW server_version')
docker rm -f "$container" >/dev/null
docker volume rm "$volume" >/dev/null
rm -rf "$socket_dir"
trap - EXIT

[[ -z "$(docker ps -a --format '{{.Names}}' | grep -Fx "$container" || true)" ]]
[[ -z "$(docker volume ls --format '{{.Name}}' | grep -Fx "$volume" || true)" ]]
[[ "$(ss -lntH | awk '{print $4}' | grep -Ec '(^|:)(5432)$' || true)" == 0 ]]

printf 'm3_unit_contracts=PASS\nm3_order_intake=PASS\nm3_idempotency=PASS\nm3_authorization=PASS\nm3_transitions=PASS\nm3_tasks_retries_dead_letters=PASS\nm3_outbox=PASS\nnetwork_isolation=PASS\ncleanup=PASS\nsocket_hardening=PASS\nsocket_dir_mode=%s\nsocket_file_mode=%s\npassword_encryption=%s\npg_hba_local_auth=%s\nnegative_local_user=%s\nresource_container=%s\nresource_volume=%s\nresource_socket=%s\npostgres_version=%s\nimage=%s\n' \
    "$socket_dir_mode" "$socket_file_mode" "$password_encryption" "$pg_hba_local_auth" \
    "$negative_local_user" "$container" "$volume" "$socket_dir" "$version" "$image"