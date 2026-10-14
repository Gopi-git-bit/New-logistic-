#!/usr/bin/env bash
set +x
set -euo pipefail
umask 077

repository_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." && pwd)
command=(bash "$repository_root/db/zippy/scripts/run_m3_core_proof.sh")
self_test=no
proof_failure() {
    printf 'status_probe=EXPECTED_FAILURE\n'
    return 37
}
case "${1:-}" in
    '') [[ $# -eq 0 ]] ;;
    --self-test) [[ $# -eq 1 ]]; command=(proof_failure); self_test=yes ;;
    *) printf 'Usage: bash %s [--self-test]\n' "$0" >&2; exit 64 ;;
esac

log_dir=$(mktemp -d /tmp/zippy-m3-proof-log.XXXXXXXX)
log_file="$log_dir/proof.log"
set +e
"${command[@]}" >"$log_file" 2>&1
proof_status=$?
set -e

printf '\nharness_exit_code=%s\n' "$proof_status" >>"$log_file" || true
tail -n 60 -- "$log_file" | awk '
    /^status_probe=EXPECTED_FAILURE$/ ||
    /^harness_exit_code=[0-9]+$/ ||
    /^(m3_[a-z_]+|network_isolation|cleanup|socket_hardening)=PASS$/ ||
    /^socket_(dir|file)_mode=[0-9]+$/ ||
    /^password_encryption=[a-z0-9-]+$/ ||
    /^pg_hba_local_auth=[a-z0-9,-]+$/ ||
    /^negative_local_user=(PASS|NOT VERIFIED)$/ ||
    /^resource_(container|volume|socket)=[^ ]+$/ ||
    /^[= ]*[0-9]+ passed(, [0-9]+ skipped)?(, [0-9]+ warnings?)? in [0-9.]+s[= ]*$/ ||
    /^[= ]*[0-9]+ failed(, [0-9]+ passed)?(, [0-9]+ skipped)? in [0-9.]+s[= ]*$/
' || true

final_status=$proof_status
if [[ "$self_test" == no && "$proof_status" -eq 0 ]]; then
    resource_container=$(sed -n 's/^resource_container=//p' "$log_file" | tail -n 1 || true)
    resource_volume=$(sed -n 's/^resource_volume=//p' "$log_file" | tail -n 1 || true)
    resource_socket=$(sed -n 's/^resource_socket=//p' "$log_file" | tail -n 1 || true)
    set +e
    bash "$repository_root/db/zippy/scripts/verify_m3_cleanup.sh" \
        "$proof_status" "$resource_container" "$resource_volume" "$resource_socket" >>"$log_file" 2>&1
    cleanup_status=$?
    set -e
    printf 'cleanup_status=%s\n' "$cleanup_status" >>"$log_file" || true
    if [[ "$cleanup_status" -ne 0 ]]; then
        final_status=$cleanup_status
        printf 'cleanup-verification=FAIL\n' || true
    else
        printf 'cleanup-verification=PASS\n' || true
    fi
fi
printf 'harness_exit_code=%s\nfinal_exit_code=%s\nprivate_log=%s\n' \
    "$proof_status" "$final_status" "$log_file" || true
exit "$final_status"