#!/usr/bin/env bash
set -euo pipefail

# Verifies exact disposable M3 proof resource cleanup and computes the combined
# exit status: a failing proof status is always preserved; a successful proof
# with failed cleanup verification exits nonzero.

usage() {
    printf 'Usage: %s <proof-status> <container> <volume> <socket-dir>\n' "$0" >&2
    exit 64
}

resources_absent() {
    local container=$1 volume=$2 socket_dir=$3
    if docker ps -a --format '{{.Names}}' | grep -Fxq -- "$container"; then
        return 1
    fi
    if docker volume ls --format '{{.Name}}' | grep -Fxq -- "$volume"; then
        return 1
    fi
    if [[ -e "$socket_dir" || -L "$socket_dir" ]]; then
        return 1
    fi
    return 0
}

if [[ "${1:-}" == "--self-test" ]]; then
    [[ $# -eq 1 ]] || usage
    absent_container="zippy-m3-cleanup-selftest-absent-container"
    absent_volume="zippy_m3_cleanup_selftest_absent_volume"
    absent_socket=$(mktemp -u "/tmp/zippy-m3-cleanup-probe-absent.XXXXXXXX")
    existing_socket="/tmp"
    failures=0
    probe() {
        local expected=$1
        shift
        local actual=0
        bash "$0" "$@" >/dev/null 2>&1 || actual=$?
        if [[ "$actual" -ne "$expected" ]]; then
            printf 'cleanup-probe=FAIL expected=%s actual=%s proof_status=%s socket=%s\n' \
                "$expected" "$actual" "$1" "$4" >&2
            failures=1
        else
            printf 'cleanup-probe=PASS expected=%s actual=%s\n' "$expected" "$actual"
        fi
    }
    # proof fails / cleanup passes -> preserve failing proof status
    probe 37 37 "$absent_container" "$absent_volume" "$absent_socket"
    # proof succeeds / cleanup fails -> nonzero
    probe 1 0 "$absent_container" "$absent_volume" "$existing_socket"
    # proof fails / cleanup fails -> preserve failing proof status
    probe 37 37 "$absent_container" "$absent_volume" "$existing_socket"
    # proof succeeds / cleanup passes -> zero
    probe 0 0 "$absent_container" "$absent_volume" "$absent_socket"
    exit "$failures"
fi

[[ $# -eq 4 ]] || usage
[[ "$1" =~ ^[0-9]+$ ]] || usage
proof_status=$1
if [[ "$proof_status" -ne 0 ]]; then
    exit "$proof_status"
fi
if [[ -z "$2" || -z "$3" || -z "$4" ]]; then
    printf 'cleanup verification failed: missing resource names\n' >&2
    exit 1
fi
if ! resources_absent "$2" "$3" "$4"; then
    printf 'cleanup verification failed: %s %s %s\n' "$2" "$3" "$4" >&2
    exit 1
fi
printf 'cleanup-verification=PASS\n'
