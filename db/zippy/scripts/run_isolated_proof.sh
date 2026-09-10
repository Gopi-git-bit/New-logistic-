#!/usr/bin/env bash
set -euo pipefail

readonly image='postgres@sha256:f1c3376c26f2609ab9f29f71f824103fe2fcd8ee0346485cb6122a4f93df6f94'
readonly expected_image_id='sha256:f1c3376c26f2609ab9f29f71f824103fe2fcd8ee0346485cb6122a4f93df6f94'
readonly repository_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." && pwd)
readonly suffix="$(date -u +%Y%m%d%H%M%S)_$(tr -d '-' </proc/sys/kernel/random/uuid | cut -c1-8)"
readonly container="zippy-m2-disposable-${suffix//_/-}"
readonly volume="zippy_m2_disposable_${suffix}_data"
readonly database="zippy_m2_disposable_${suffix}"
readonly marker="$(cat /proc/sys/kernel/random/uuid)"
readonly super_password="$(tr -d '-' </proc/sys/kernel/random/uuid)$(tr -d '-' </proc/sys/kernel/random/uuid)"
readonly migration_password="$(tr -d '-' </proc/sys/kernel/random/uuid)$(tr -d '-' </proc/sys/kernel/random/uuid)"
readonly app_password="$(tr -d '-' </proc/sys/kernel/random/uuid)$(tr -d '-' </proc/sys/kernel/random/uuid)"
readonly readonly_password="$(tr -d '-' </proc/sys/kernel/random/uuid)$(tr -d '-' </proc/sys/kernel/random/uuid)"

cleanup() {
    docker rm -f "$container" >/dev/null 2>&1 || true
    docker volume rm "$volume" >/dev/null 2>&1 || true
}
trap cleanup EXIT

[[ "$(docker image inspect "$image" --format '{{.Id}}')" == "$expected_image_id" ]]
[[ -z "$(docker ps -a --format '{{.Names}}' | grep -Fx "$container" || true)" ]]
[[ -z "$(docker volume ls --format '{{.Name}}' | grep -Fx "$volume" || true)" ]]
[[ "$(ss -lntH | awk '{print $4}' | grep -Ec '(^|:)(5432)$' || true)" == 0 ]]

docker volume create "$volume" >/dev/null
docker run -d \
    --name "$container" \
    --network none \
    --mount "type=volume,source=$volume,target=/var/lib/postgresql/data" \
    --mount "type=bind,source=$repository_root,target=/workspace,readonly" \
    --health-cmd="pg_isready -U zippy_m2_runner -d $database" \
    --health-interval=1s \
    --health-timeout=1s \
    --health-retries=60 \
    -e POSTGRES_USER=zippy_m2_runner \
    -e POSTGRES_PASSWORD="$super_password" \
    -e POSTGRES_DB="$database" \
    "$image" >/dev/null

ready=false
for _ in {1..120}; do
    ready_events=$(docker logs "$container" 2>&1 | grep -c 'database system is ready to accept connections' || true)
    if [[ "$ready_events" -ge 2 ]] \
       && docker exec "$container" pg_isready -U zippy_m2_runner -d "$database" >/dev/null 2>&1; then
        ready=true
        break
    fi
    read -r -t 1 _ </dev/null || true
done
[[ "$ready" == true ]]
[[ "$(docker inspect -f '{{.HostConfig.NetworkMode}}' "$container")" == none ]]
[[ -z "$(docker port "$container")" ]]
[[ "$(docker inspect -f '{{range .Mounts}}{{if eq .Destination "/workspace"}}{{.RW}}{{end}}{{end}}' "$container")" == false ]]
[[ "$(docker inspect -f '{{range .Mounts}}{{if eq .Destination "/var/lib/postgresql/data"}}{{.Name}}{{end}}{{end}}' "$container")" == "$volume" ]]
[[ "$(docker inspect -f '{{.Image}}' "$container")" == "$expected_image_id" ]]

docker exec -i -e PGPASSWORD="$super_password" "$container" \
    psql -X --set=ON_ERROR_STOP=1 --quiet -U zippy_m2_runner -d postgres \
    --set=database_name="$database" --set=marker="$marker" --set=container_name="$container" \
    --set=volume_name="$volume" --set=image_digest="$image" <<'SQL'
ALTER DATABASE :"database_name" SET "zippy.m2_marker" TO :'marker';
ALTER DATABASE :"database_name" SET "zippy.m2_container" TO :'container_name';
ALTER DATABASE :"database_name" SET "zippy.m2_volume" TO :'volume_name';
ALTER DATABASE :"database_name" SET "zippy.m2_image_digest" TO :'image_digest';
SQL

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

run_app_psql() {
    docker exec "${common_env[@]}" \
        -e PGUSER=zippy_m2_app_login -e PGPASSWORD="$app_password" "$container" \
        psql -X --set=ON_ERROR_STOP=1 --quiet --no-psqlrc "$@"
}

run_readonly_psql() {
    docker exec "${common_env[@]}" \
        -e PGUSER=zippy_m2_readonly_login -e PGPASSWORD="$readonly_password" "$container" \
        psql -X --set=ON_ERROR_STOP=1 --quiet --no-psqlrc "$@"
}

run_superuser_psql() {
    docker exec "${common_env[@]}" \
        -e PGUSER=zippy_m2_runner -e PGPASSWORD="$super_password" "$container" \
        psql -X --set=ON_ERROR_STOP=1 --quiet --no-psqlrc "$@"
}

run_assertions() {
    run_superuser_psql --file=/workspace/db/zippy/tests/setup.sql
    run_app_psql --set=expected_session_user=zippy_m2_app_login --file=/workspace/db/zippy/tests/verify.sql
    run_app_psql --set=expected_session_user=zippy_m2_app_login --file=/workspace/db/zippy/tests/verify_security.sql
    run_migrator psql -X --set=ON_ERROR_STOP=1 --quiet --no-psqlrc --file=/workspace/db/zippy/tests/verify_admin_control.sql
    run_readonly_psql --set=expected_session_user=zippy_m2_readonly_login --file=/workspace/db/zippy/tests/verify_readonly.sql
}

run_migrator /workspace/db/zippy/scripts/migrate.sh up
run_assertions
docker exec "${common_env[@]}" -e PGUSER=zippy_m2_app_login -e PGPASSWORD="$app_password" "$container" \
    pgbench -n -U zippy_m2_app_login -d "$database" -c 2 -j 2 -t 1 \
    -f /workspace/db/zippy/tests/concurrent_claim.pgbench.sql >/dev/null
run_app_psql --set=expected_session_user=zippy_m2_app_login --file=/workspace/db/zippy/tests/verify_concurrency.sql
run_migrator /workspace/db/zippy/tests/verify_runner_rejection.sh

run_migrator env ZIPPY_CONFIRM_DISPOSABLE_DOWN="$database" /workspace/db/zippy/scripts/migrate.sh down
[[ "$(run_superuser_psql --tuples-only --no-align --command="SELECT count(*) FROM pg_namespace WHERE nspname = 'zippy'")" == 0 ]]
[[ "$(run_superuser_psql --tuples-only --no-align --command="SELECT count(*) FROM pg_roles WHERE rolname IN ('zippy_migrator','zippy_app','zippy_readonly')")" == 3 ]]

run_migrator /workspace/db/zippy/scripts/migrate.sh up
run_assertions
run_migrator env ZIPPY_CONFIRM_DISPOSABLE_DOWN="$database" /workspace/db/zippy/scripts/migrate.sh down

docker exec "${common_env[@]}" \
    -e PGUSER=zippy_m2_runner -e PGPASSWORD="$super_password" \
    -e ZIPPY_CONFIRM_DISPOSABLE_ROLE_TEARDOWN="$database:$container:$volume" \
    "$container" /workspace/db/zippy/scripts/roles.sh teardown
[[ "$(run_superuser_psql --tuples-only --no-align --command="SELECT count(*) FROM pg_roles WHERE rolname IN ('zippy_migrator','zippy_app','zippy_readonly','zippy_m2_migration_login','zippy_m2_app_login','zippy_m2_readonly_login')")" == 0 ]]
[[ "$(run_superuser_psql --tuples-only --no-align --command="SELECT count(*) FROM pg_roles WHERE rolname = 'zippy_m2_runner' AND rolsuper AND rolcanlogin")" == 1 ]]

version=$(run_superuser_psql --tuples-only --no-align --command='SHOW server_version')
docker rm -f "$container" >/dev/null
docker volume rm "$volume" >/dev/null
trap - EXIT

[[ -z "$(docker ps -a --format '{{.Names}}' | grep -Fx "$container" || true)" ]]
[[ -z "$(docker volume ls --format '{{.Name}}' | grep -Fx "$volume" || true)" ]]
[[ "$(ss -lntH | awk '{print $4}' | grep -Ec '(^|:)(5432)$' || true)" == 0 ]]

printf 'fresh_up=PASS\nrestricted_app_rls_and_privileges=PASS\nrestricted_readonly=PASS\nbehavioral_assertions=PASS\nconcurrent_claim=PASS\nstale_lease_recovery=PASS\nrunner_rejections=PASS\nschema_down_roles_preserved=PASS\nreapply_assertions=PASS\nseparate_role_teardown=PASS\ncleanup=PASS\npostgres_version=%s\nimage=%s\nimage_id=%s\n' \
    "$version" "$image" "$expected_image_id"