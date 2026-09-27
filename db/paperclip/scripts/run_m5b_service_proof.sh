#!/usr/bin/env bash
# One fresh, isolated M5-B proof. Never consumes an incoming database URL.
set -euo pipefail
umask 077
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." && pwd)
image='postgres@sha256:f1c3376c26f2609ab9f29f71f824103fe2fcd8ee0346485cb6122a4f93df6f94'
[[ $# == 0 ]] || exit 2
suffix="$(date -u +%Y%m%d%H%M%S)_$(openssl rand -hex 4)"
name="paperclip-m5b-${suffix//_/-}"
volume="paperclip_m5b_${suffix}"
database="paperclip_m5_disposable_${suffix}"
socket=$(mktemp -d /tmp/paperclip-m5b.XXXXXX)
envfile=$(mktemp /tmp/paperclip-m5b-env.XXXXXX)
password=$(openssl rand -hex 24)
app_password=$(openssl rand -hex 24)
envelope_key=$(openssl rand -hex 32)
log=${M5B_PROOF_LOG:?caller must supply the private proof log path}
[[ -f "$log" && $(stat -c %a "$log") == 600 ]] || exit 2
watchdog=''
fail() { printf 'M5B_FAILURE=%s\n' "$1"; exit 1; }
no_listener() { [[ -z "$(ss -H -ltn 'sport = :5432')" ]]; }
cleanup() {
    local status=$? cleanup_status=0
    trap - EXIT
    if [[ -n "$watchdog" ]]; then kill "$watchdog" 2>/dev/null || true; wait "$watchdog" 2>/dev/null || true; fi
    if docker container inspect "$name" >/dev/null 2>&1; then docker rm -f "$name" >/dev/null || cleanup_status=1; fi
    if docker volume inspect "$volume" >/dev/null 2>&1; then docker volume rm "$volume" >/dev/null || cleanup_status=1; fi
    rm -rf -- "$socket"
    rm -f -- "$envfile"
    if docker container inspect "$name" >/dev/null 2>&1 || docker volume inspect "$volume" >/dev/null 2>&1 || [[ -e "$socket" || -e "$envfile" ]]; then cleanup_status=1; fi
    if no_listener; then printf 'host_port_5432=PASS\n'; else cleanup_status=1; printf 'host_port_5432=FAIL\n'; fi
    if (( cleanup_status == 0 )); then printf 'exact_cleanup=PASS\n'; else printf 'exact_cleanup=FAIL\n'; status=1; fi
    unset password app_password envelope_key
    exit "$status"
}
trap cleanup EXIT
trap 'fail interrupted' TERM INT
printf 'container=%s\nvolume=%s\nsocket=%s\nenvironment_file=%s\n' "$name" "$volume" "$socket" "$envfile"
no_listener || fail host_port_5432_preexisting
# Image inspection only; never launch an auxiliary container or pull a different image.
docker image inspect "$image" >/dev/null
chown 999:999 "$socket"
chmod 700 "$socket"
{
    printf 'POSTGRES_USER=paperclip_m5_runner\nPOSTGRES_PASSWORD=%s\nPOSTGRES_DB=%s\n' "$password" "$database"
    printf 'POSTGRES_INITDB_ARGS=--auth-local=scram-sha-256 --auth-host=scram-sha-256\n'
    printf 'PGUSER=paperclip_m5_runner\nPGPASSWORD=%s\nPGDATABASE=%s\nPGHOST=/var/run/postgresql\n' "$password" "$database"
    printf 'PAPERCLIP_ALLOW_DISPOSABLE_DB=YES\nM5B_APP_PASSWORD=%s\n' "$app_password"
} > "$envfile"
docker create --name "$name" --network none --env-file "$envfile" \
    --mount "type=volume,source=${volume},target=/var/lib/postgresql/data" \
    --mount "type=bind,source=${socket},target=/var/run/postgresql" \
    --mount "type=bind,source=${root},target=/workspace,readonly" \
    "$image" postgres -c 'listen_addresses=' -c unix_socket_directories=/var/run/postgresql >/dev/null
docker start "$name" >/dev/null
deadline=$((SECONDS + 60))
while :; do
    [[ $(docker inspect --format '{{.State.Running}}' "$name") == true ]] || fail container_exited_before_readiness
    if [[ $(docker exec "$name" cat /proc/1/comm 2>/dev/null || true) == postgres ]] && docker exec --env-file "$envfile" "$name" pg_isready -q; then break; fi
    (( SECONDS < deadline )) || fail readiness_timeout
    sleep 1
done
parent=$$
(
    while sleep 1; do
        if [[ $(docker inspect --format '{{.State.Running}}' "$name" 2>/dev/null || true) != true ]]; then
            printf 'M5B_FAILURE=container_exited_during_proof\n'
            kill -TERM "$parent"
            exit 1
        fi
    done
) &
watchdog=$!
chmod 700 "$socket"
[[ $(stat -c %u:%g "$socket") == 999:999 ]] || fail socket_owner
(( (8#$(stat -c %a "$socket") & 8#777) == 8#700 )) || fail socket_permissions
[[ -S "$socket/.s.PGSQL.5432" ]] || fail socket_missing
[[ $(docker inspect --format '{{.HostConfig.NetworkMode}}' "$name") == none ]] || fail network_mode
[[ $(docker inspect --format '{{json .HostConfig.PortBindings}}' "$name") == '{}' ]] || fail port_binding
[[ -z $(docker exec --env-file "$envfile" "$name" psql -X -tAc 'SHOW listen_addresses') ]] || fail tcp_listener
[[ $(docker exec --env-file "$envfile" "$name" psql -X -tAc "SELECT string_agg(DISTINCT auth_method, ',') FROM pg_hba_file_rules WHERE type='local'") == scram-sha-256 ]] || fail local_auth
printf 'network_isolation=PASS\nsocket_scram=PASS\n'
# The role/bootstrap and migration files are unchanged. Only synthetic login passwords are assigned.
docker exec -i --env-file "$envfile" "$name" bash -s >>"$log" 2>&1 <<'SQL'
set -euo pipefail
cd /workspace
bash db/paperclip/scripts/roles.sh bootstrap
bash db/paperclip/scripts/migrate.sh up
psql -X -v ON_ERROR_STOP=1 <<'PASSWORD'
\getenv app_password M5B_APP_PASSWORD
SELECT format('ALTER ROLE paperclip_m5_app_login PASSWORD %L', :'app_password') \gexec
PASSWORD
psql -X -v ON_ERROR_STOP=1 -f db/paperclip/tests/setup.sql
psql -X -v ON_ERROR_STOP=1 -f db/paperclip/tests/verify.sql
psql -X -v ON_ERROR_STOP=1 -f db/paperclip/tests/verify_security.sql
psql -X -q -tA -v ON_ERROR_STOP=1 -f db/paperclip/tests/verify_concurrency.sql >/dev/null
printf 'm5a_security_regression=PASS\n'
# Reset synthetic fixtures before exercising the service; no role/grant changes.
bash db/paperclip/scripts/migrate.sh down
bash db/paperclip/scripts/migrate.sh up
psql -X -v ON_ERROR_STOP=1 -f db/paperclip/tests/setup.sql
SQL
printf 'bootstrap_and_fixture_reset=PASS\n'
# The test process has no network namespace connectivity and an explicitly constructed environment.
# Passwords are passed through private stdin, never command arguments or printed environment.
{
printf '%s\n%s\n%s\n%s\n' "$app_password" "$envelope_key" "$socket" "$database" | \
    unshare --net env -i PATH="$PATH" PYTHONDONTWRITEBYTECODE=1 "$root/.venv/bin/python" -c '
import os, subprocess, sys
password, key, socket, database = sys.stdin.read().splitlines()
env = {"PATH": os.environ["PATH"], "PYTHONDONTWRITEBYTECODE": "1",
       "PAPERCLIP_DISPOSABLE_PROOF": "YES",
       "PAPERCLIP_DATABASE_URL": f"host={socket} dbname={database} user=paperclip_m5_app_login password={password} connect_timeout=3",
       "PAPERCLIP_OWNER_SUBJECT": "paperclip-owner-test",
       "PAPERCLIP_EXECUTOR_SUBJECT": "paperclip-executor-test",
       "PAPERCLIP_POLICY_ID": "11111111-1111-1111-1111-111111111113",
       "PAPERCLIP_AGENT_BINDINGS_JSON": "{\"paperclip-agent-test\":\"11111111-1111-1111-1111-111111111112\"}",
       "PAPERCLIP_ENVELOPE_SIGNING_KEY": key, "PAPERCLIP_ENVELOPE_TTL_SECONDS": "300"}
root = sys.argv[1]
result = subprocess.run([sys.executable, "-m", "pytest", "api/tests_m5", "-q", "-s", "--tb=short", "-p", "no:cacheprovider", "--junitxml=" + socket + "/results.xml"], cwd=root, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
output = result.stdout
if any(secret in output for secret in (password, key, env["PAPERCLIP_DATABASE_URL"])):
    print("M5B_FAILURE=test_output_secret_detected")
    sys.exit(1)
print(output, end="")
if result.returncode:
    sys.exit(result.returncode)
import xml.etree.ElementTree as ET
suite = ET.parse(socket + "/results.xml").getroot()
assert not suite.findall(".//skipped"), "required M5-B tests skipped"
assert not suite.findall(".//failure") and not suite.findall(".//error")
print("m5b_tests=PASS count=" + str(len(suite.findall(".//testcase"))) + " skipped=0")
print("m5b_integration_security=PASS")
' "$root"
} >>"$log" 2>&1
pytest_status=$?
if [[ ${pytest_status} -ne 0 ]]; then
    fail "M5-B Python tests failed (pytest exit=${pytest_status})"
fi
docker exec -i --env-file "$envfile" "$name" bash -s >>"$log" 2>&1 <<'SQL'
set -euo pipefail
cd /workspace
bash db/paperclip/scripts/migrate.sh down
[[ $(psql -X -tAc "SELECT count(*) FROM pg_namespace WHERE nspname='paperclip'") == 0 ]]
printf 'rollback=PASS\n'
bash db/paperclip/scripts/migrate.sh up
psql -X -v ON_ERROR_STOP=1 -f db/paperclip/tests/setup.sql
psql -X -v ON_ERROR_STOP=1 -f db/paperclip/tests/verify.sql
psql -X -v ON_ERROR_STOP=1 -f db/paperclip/tests/verify_security.sql
printf 'reapply=PASS\n'
SQL
# Compare exact generated secrets and generic credential patterns without printing their values.
printf '%s\n%s\n%s\n' "$password" "$app_password" "$envelope_key" | "$root/.venv/bin/python" -c '
import re, sys
secrets = sys.stdin.read().splitlines()
text = open(sys.argv[1]).read()
patterns = r"(?i)postgres(?:ql)?://|bearer\s+[A-Za-z0-9._-]+|password\s*=\s*[^\s]+|eyJ[A-Za-z0-9_-]+\.eyJ|sk_live_"
assert not any(secret in text for secret in secrets) and not re.search(patterns, text), "secret-pattern match"
print("secret_pattern_matches=0\nsecret_scan=PASS")
' "$log"
printf 'm5b_disposable_proof=PASS\n'
