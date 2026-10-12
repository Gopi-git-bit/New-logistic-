#!/usr/bin/env bash
# Hosted CI only. No incoming database URL or external service credential.
set +x
set -euo pipefail
umask 077
[[ $# == 1 && ${GITHUB_ACTIONS:-} == true && $(id -u) == 0 ]] || exit 64
proof=$1
case "$proof" in operations|governance) ;; *) exit 64 ;; esac
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
[[ -x "$root/.venv/bin/python" ]] || exit 65
[[ -z $(ss -H -ltn 'sport = :5432') ]] || exit 66
private_dir=$(mktemp -d /tmp/zippy-ci-proof.XXXXXXXX)
log="$private_dir/proof.log"
touch "$log"
chmod 600 "$log"
# Resource cleanup belongs to each existing harness; this trap removes only
# this wrapper's private log. Do not upload logs containing generated secrets.
trap 'rm -rf -- "$private_dir"' EXIT
set +e
if [[ "$proof" == operations ]]; then
    unshare --net env -i PATH="$PATH" PYTHONDONTWRITEBYTECODE=1 \
        ZIPPY_M4_PYTHON="$root/.venv/bin/python" \
        bash "$root/db/zippy/scripts/run_m4_finance_proof.sh" >>"$log" 2>&1
else
    unshare --net env -i PATH="$PATH" PYTHONDONTWRITEBYTECODE=1 M5B_PROOF_LOG="$log" \
        bash "$root/db/paperclip/scripts/run_m5b_service_proof.sh" >>"$log" 2>&1
fi
status=$?
set -e
# Publish only fixed proof markers and numeric summaries. Full SQL/pytest
# diagnostics remain private even on failure; never print credential strings.
"$root/.venv/bin/python" - "$log" <<'PY'
import re
import sys

patterns = (
    r"(?:m[3456][a-z0-9_]*|image_identity|network_isolation|cleanup|socket_hardening|socket_scram|bootstrap_and_fixture_reset|exact_cleanup|host_port_5432|rollback|reapply|secret_scan)=PASS",
    r"image_id=sha256:[0-9a-f]{64}",
    r"negative_local_user=(?:PASS|NOT VERIFIED)",
    r"(?:socket_dir_mode|socket_file_mode|secret_pattern_matches)=[0-9]+",
    r"(?:password_encryption|pg_hba_local_auth)=scram-sha-256",
    r"database_proof_tests=PASS proof=(?:operations|governance) total=[0-9]+ integration=[0-9]+ skipped=0",
    r"m5b_tests=PASS count=[0-9]+ skipped=0",
    r"m5b_concurrency=PASS successes=1 denials=1",
    r"[= ]*[0-9]+ passed(?:, [0-9]+ skipped)?(?:, [0-9]+ warnings?)? in [0-9.]+s[= ]*",
    r"[= ]*[0-9]+ failed(?:, [0-9]+ passed)?(?:, [0-9]+ skipped)?(?:, [0-9]+ warnings?)? in [0-9.]+s[= ]*",
    r"DATABASE_PROOF_REPORT_REJECTED",
)
with open(sys.argv[1]) as log:
    for line in log:
        line = line.rstrip("\n")
        if any(re.fullmatch(pattern, line) for pattern in patterns):
            print(line)
PY
printf 'proof=%s exit_code=%s\n' "$proof" "$status"
exit "$status"
