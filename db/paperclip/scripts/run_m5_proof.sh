#!/usr/bin/env bash
set -euo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." && pwd)
image='postgres@sha256:f1c3376c26f2609ab9f29f71f824103fe2fcd8ee0346485cb6122a4f93df6f94'
mode=${1:-proof}
[[ "$mode" == proof || "$mode" == --static-check ]] || { printf 'usage: %s [--static-check]\n' "$0" >&2; exit 2; }
suffix="$(date -u +%Y%m%d%H%M%S)_$(openssl rand -hex 4)"
name="paperclip-m5-${suffix//_/-}"
volume="paperclip_m5_${suffix}"
database="paperclip_m5_disposable_${suffix}"
user=paperclip_m5_runner
password=$(openssl rand -hex 24)
socket=$(mktemp -d /tmp/paperclip-m5.XXXXXX)
envfile=$(mktemp /tmp/paperclip-m5-env.XXXXXX)
log=$(mktemp /tmp/paperclip-m5-proof.XXXXXX)
chmod 600 "$envfile" "$log"

cleanup() {
	local status=$?
	docker rm -f "$name" >/dev/null 2>&1 || true
	docker volume rm "$volume" >/dev/null 2>&1 || true
	rm -rf -- "$socket"
	rm -f -- "$envfile"
	exit "$status"
}
trap cleanup EXIT

fail() { printf 'M5 harness failure: %s (log %s)\n' "$*" >&2; exit 1; }
redact() { sed -E "s/${password}/[REDACTED]/g"; }

postgres_identity=$(docker run --rm --network none --user postgres --entrypoint id "$image" | sed -nE 's/^uid=([0-9]+).*gid=([0-9]+).*/\1:\2/p')
[[ "$postgres_identity" == '999:999' ]] || fail "unexpected PostgreSQL identity"
chown "$postgres_identity" "$socket"
chmod 0700 "$socket"

{
	printf 'POSTGRES_USER=%s\n' "$user"
	printf 'POSTGRES_PASSWORD=%s\n' "$password"
	printf 'POSTGRES_DB=%s\n' "$database"
	printf 'POSTGRES_INITDB_ARGS=--auth-local=scram-sha-256\n'
	printf 'PGUSER=%s\n' "$user"
	printf 'PGPASSWORD=%s\n' "$password"
	printf 'PGDATABASE=%s\n' "$database"
	printf 'PGHOST=/var/run/postgresql\n'
	printf 'PAPERCLIP_ALLOW_DISPOSABLE_DB=YES\n'
} >"$envfile"

create_args=(
	--name "$name"
	--network none
	--env-file "$envfile"
	--mount "type=volume,source=${volume},target=/var/lib/postgresql/data"
	--mount "type=bind,source=${socket},target=/var/run/postgresql"
	--mount "type=bind,source=${root},target=/workspace,readonly"
	"$image" postgres
	-c "listen_addresses="
	-c "unix_socket_directories=/var/run/postgresql"
)

assert_invocation() {
	local index image_index=-1 postgres_index=-1 argument
	for index in "${!create_args[@]}"; do
		argument=${create_args[$index]}
		case "$argument" in
			-p|-P|--publish|--publish-all|--publish=*|--network=host|--net=host) fail "port publication or host network rejected" ;;
		esac
		if [[ "$argument" == host && $index -gt 0 && "${create_args[$((index - 1))]}" =~ ^--net(work)?$ ]]; then
			fail "host network rejected"
		fi
		if [[ "$argument" == "$image" && $image_index -lt 0 ]]; then image_index=$index; fi
		if [[ "$argument" == postgres && $image_index -ge 0 && $postgres_index -lt 0 ]]; then postgres_index=$index; fi
	done
	(( image_index >= 0 )) || fail "pinned image missing"
	(( postgres_index == image_index + 1 )) || fail "postgres command must immediately follow the image"
	for index in "${!create_args[@]}"; do
		if [[ "${create_args[$index]}" == -c ]]; then
			(( index > postgres_index )) || fail "-c argument precedes postgres command"
		fi
	done
	printf 'DOCKER_CREATE:'; printf ' %q' docker create "${create_args[@]}"; printf '\n'
	printf 'STATIC_INVOCATION=PASS image_index=%s postgres_index=%s\n' "$image_index" "$postgres_index"
}

assert_invocation

if [[ "$mode" == --static-check ]]; then
	docker create "${create_args[@]}" >/dev/null
	printf 'CREATE_PATH=%s\n' "$(docker inspect --format '{{.Path}}' "$name")"
	printf 'CREATE_ARGS=%s\n' "$(docker inspect --format '{{json .Args}}' "$name")"
	printf 'CREATE_NETWORK=%s\n' "$(docker inspect --format '{{.HostConfig.NetworkMode}}' "$name")"
	printf 'CREATE_PORTS=%s\n' "$(docker inspect --format '{{json .HostConfig.PortBindings}}' "$name")"
	printf 'CREATE_MOUNTS=%s\n' "$(docker inspect --format '{{range .Mounts}}{{.Type}}:{{.Destination}}:{{.RW}} {{end}}' "$name")"
	exit 0
fi

docker create "${create_args[@]}" >/dev/null
docker start "$name" >/dev/null
deadline=$((SECONDS + 60))
while :; do
	running=$(docker inspect --format '{{.State.Running}}' "$name" 2>/dev/null || printf false)
	if [[ "$running" != true ]]; then
		exit_code=$(docker inspect --format '{{.State.ExitCode}}' "$name" 2>/dev/null || printf unknown)
		docker logs "$name" 2>&1 | redact >>"$log" || true
		tail -n 20 "$log" >&2
		fail "PostgreSQL exited before readiness (exit=${exit_code})"
	fi
	# The entrypoint runs a temporary init server before exec'ing the final postgres as PID 1.
	if [[ "$(docker exec "$name" cat /proc/1/comm 2>/dev/null || true)" == postgres ]] \
		&& docker exec --env-file "$envfile" "$name" pg_isready -q; then
		break
	fi
	if (( SECONDS >= deadline )); then
		docker logs "$name" 2>&1 | redact >>"$log" || true
		tail -n 20 "$log" >&2
		fail "PostgreSQL readiness deadline exceeded"
	fi
	sleep 1
done

chmod 0700 "$socket"
[[ "$(stat -c %u:%g "$socket")" == "$postgres_identity" ]] || fail "socket directory owner"
(( (8#$(stat -c %a "$socket") & 8#777) == 8#700 )) || fail "socket directory permissions"
[[ -S "$socket/.s.PGSQL.5432" ]] || fail "socket missing from private directory"
[[ "$(find "$socket" -mindepth 1 -type s | wc -l)" == 1 ]] || fail "unexpected socket files"
[[ "$(docker inspect --format '{{.HostConfig.NetworkMode}}' "$name")" == none ]] || fail "network mode"
[[ "$(docker inspect --format '{{json .NetworkSettings.Ports}}' "$name")" == '{}' ]] || fail "published ports"
[[ -z "$(docker exec --env-file "$envfile" "$name" psql -X -tAc 'SHOW listen_addresses')" ]] || fail "TCP listener configured"
[[ "$(docker exec --env-file "$envfile" "$name" psql -X -tAc "SELECT string_agg(DISTINCT auth_method, ',') FROM pg_hba_file_rules WHERE type = 'local'")" == scram-sha-256 ]] || fail "local authentication is not SCRAM"
if docker exec --env-file "$envfile" --user 65534:65534 "$name" psql -X -tAc 'SELECT 1' >>"$log" 2>&1; then
	fail "unrelated UID connected"
fi
grep -q 'Permission denied' "$log" || fail "unrelated UID denial was not a socket permission denial"
printf 'socket_isolation=PASS socket_dir_mode=%s owner=%s\n' "$(stat -c %a "$socket")" "$(stat -c %u:%g "$socket")" >>"$log"

set +e
docker exec -i --env-file "$envfile" "$name" bash -s >>"$log" 2>&1 <<'SQL'
set -euo pipefail
cd /workspace
bash db/paperclip/scripts/roles.sh bootstrap
bash db/paperclip/scripts/migrate.sh up
psql -X -v ON_ERROR_STOP=1 -f db/paperclip/tests/setup.sql
psql -X -v ON_ERROR_STOP=1 -f db/paperclip/tests/verify.sql
psql -X -v ON_ERROR_STOP=1 -f db/paperclip/tests/verify_security.sql
grant_id=$(psql -X -q -tA -v ON_ERROR_STOP=1 -f db/paperclip/tests/verify_concurrency.sql | tail -n 1)
[[ "$grant_id" =~ ^[0-9a-f-]{36}$ ]] || { echo 'concurrency grant preparation failed'; exit 1; }
hash=$(psql -X -q -tA -c "SELECT encode(public.digest('{\"ref\":\"conc\"}'::jsonb::text, 'sha256'), 'hex');")
consume_sql="SET ROLE paperclip_app; SELECT set_config('paperclip.tenant_id','11111111-1111-1111-1111-111111111111',false); SELECT pg_advisory_lock_shared(5005); SELECT paperclip.consume_grant('${grant_id}','11111111-1111-1111-1111-111111111112','REFUND','ZIPPY','order','concurrency','${hash}');"
psql -X -q -c "SELECT pg_advisory_lock(5005); SELECT pg_sleep(2); SELECT pg_advisory_unlock(5005);" >/dev/null &
barrier=$!
sleep 0.5
for racer in 1 2; do
	( rc=0; psql -X -q -tA -v ON_ERROR_STOP=1 -c "$consume_sql" >/tmp/m5-racer-$racer.out 2>&1 || rc=$?; echo "$rc" >/tmp/m5-racer-$racer.rc ) &
done
wait
successes=0
for racer in 1 2; do
	if grep -q 'GRANT_CONSUMED' "/tmp/m5-racer-$racer.out"; then
		successes=$((successes + 1))
	fi
done
[[ $successes == 1 ]] || { echo "concurrent consumption successes=${successes}"; exit 1; }
grep -q 'GRANT_CONSUMPTION_DENIED' /tmp/m5-racer-1.out /tmp/m5-racer-2.out || { echo 'losing racer was not a grant denial'; exit 1; }
attempts=$(psql -X -tA -c "SET ROLE paperclip_migrator; SELECT set_config('paperclip.tenant_id','11111111-1111-1111-1111-111111111111',false) IS NOT NULL; SELECT count(*) FROM paperclip.execution_attempts WHERE grant_id = '${grant_id}';" | tail -n 1)
[[ "$attempts" == 1 ]] || { echo "concurrent consumption attempts=${attempts}"; exit 1; }
echo "concurrency=PASS successes=${successes} attempts=${attempts}"
echo 'fresh_up_and_verify=PASS'
bash db/paperclip/scripts/migrate.sh down
[[ "$(psql -X -tAc "SELECT count(*) FROM pg_namespace WHERE nspname = 'paperclip'")" == 0 ]]
echo 'rollback=PASS'
bash db/paperclip/scripts/migrate.sh up
psql -X -v ON_ERROR_STOP=1 -f db/paperclip/tests/setup.sql
psql -X -v ON_ERROR_STOP=1 -f db/paperclip/tests/verify.sql
psql -X -v ON_ERROR_STOP=1 -f db/paperclip/tests/verify_security.sql
echo 'reapply=PASS'
SQL
status=$?
set -e
redact <"$log"
exit "$status"