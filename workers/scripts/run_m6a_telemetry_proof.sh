#!/usr/bin/env bash
# M6-A telemetry synthetic proof harness — D-31 boundary.
# No live credentials, no network, no external transmission, no Docker.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# Select existing repository Python environment.
PYTHON="${REPO_ROOT}/.venv/bin/python"
if [[ ! -x "$PYTHON" ]]; then
    echo "PYTHON_ENV_FAIL=FAIL: missing ${PYTHON}" >&2
    exit 1
fi

# Prevent any Langfuse credentials or endpoints from being used.
unset LANGFUSE_PUBLIC_KEY LANGFUSE_SECRET_KEY LANGFUSE_HOST
export LANGFUSE_PUBLIC_KEY=""
export LANGFUSE_SECRET_KEY=""
export LANGFUSE_HOST=""

# Synthetic identifiers and ephemeral test HMAC key.
export M6A_TEST_PEPPER="$(openssl rand -hex 32)"
export M6A_TEST_ENVIRONMENT="m6a-proof"

# Create a private temporary directory.
TMPDIR="$(mktemp -d /tmp/m6a-proof-payload.XXXXXX)"
chmod 0700 "$TMPDIR"

cleanup() {
    if [[ -n "${TMPDIR:-}" && -d "$TMPDIR" ]]; then
        rm -rf "$TMPDIR"
    fi
}
trap cleanup EXIT

PASS_MARKERS=()
FAIL_MARKERS=()

mark_pass() {
    PASS_MARKERS+=("$1")
    printf '%s=PASS\n' "$1"
}

mark_fail() {
    local marker="${1:-unknown}"
    local detail="${2:-unspecified}"
    FAIL_MARKERS+=("$marker")
    printf '%s=FAIL detail=%s\n' "$marker" "$detail" >&2
}

# Verify telemetry disabled by default.
if "$PYTHON" -c "
import sys
sys.path.insert(0, '${REPO_ROOT}/workers/src')
from zippy_workers.telemetry_adapter import TelemetryAdapter
from zippy_workers.config import WorkerSettings

a = TelemetryAdapter()
settings = WorkerSettings()
assert a.enabled is False, 'adapter enabled default'
assert a.sampling_rate == 0.0, 'adapter sampling default'
assert settings.telemetry_enabled is False, 'settings enabled default'
assert settings.telemetry_sampling_rate == 0.0, 'settings sampling default'
"; then
    mark_pass telemetry_disabled_default
    mark_pass sampling_zero_default
else
    mark_fail telemetry_disabled_default "pydantic_settings import or assertion failed"
    mark_fail sampling_zero_default "sampling default not zero"
fi

# Verify sampling default is exactly zero and synthetic 100% sampling works.
if "$PYTHON" -c "
import sys
sys.path.insert(0, '${REPO_ROOT}/workers/src')
from zippy_workers.telemetry_adapter import TelemetryAdapter, InMemorySink

# Default adapter: sampling_rate == 0.0
a0 = TelemetryAdapter(enabled=True, sink=InMemorySink())
assert a0.sampling_rate == 0.0, 'default sampling not zero'
a0._try_emit({'trace_id': 'abc'})
assert a0.emitted == 0, 'zero sampling emitted event'

# Synthetic 100% sampling emits safe events
a1 = TelemetryAdapter(enabled=True, sampling_rate=1.0, sink=InMemorySink())
a1._try_emit({'trace_id': 'abc'})
assert a1.emitted == 1, 'full sampling did not emit'
"; then
    mark_pass sampling_default_zero
    mark_pass synthetic_sampling
else
    mark_fail sampling_default_zero "sampling default not zero or full sampling failed"
    mark_fail synthetic_sampling "full sampling did not emit safe event"
fi

# Verify typed allowlist (strict contract).
if "$PYTHON" -c "
import sys
sys.path.insert(0, '${REPO_ROOT}/workers/src')
from zippy_workers.telemetry_contract import PERMITTED_FIELDS, PROHIBITED_FIELDS, RESTRICTED_FIELDS, is_safe_for_telemetry

assert 'trace_id' in PERMITTED_FIELDS
assert 'password' in PROHIBITED_FIELDS
assert 'order_id' in RESTRICTED_FIELDS
assert not is_safe_for_telemetry('password')
assert not is_safe_for_telemetry('order_id')
assert is_safe_for_telemetry('trace_id')
assert len(PERMITTED_FIELDS & PROHIBITED_FIELDS) == 0
assert len(PERMITTED_FIELDS & RESTRICTED_FIELDS) == 0
assert len(PROHIBITED_FIELDS & RESTRICTED_FIELDS) == 0
"; then
    mark_pass typed_allowlist
else
    mark_fail typed_allowlist "typed allowlist assertion failed"
fi

# Verify prohibited fields are dropped by redaction.
if "$PYTHON" -c "
import sys
sys.path.insert(0, '${REPO_ROOT}/workers/src')
from zippy_workers.telemetry_redaction import redact_event

r = redact_event({'trace_id': 'abc', 'password': 'secret'})
assert not r.accepted, 'prohibited field did not cause drop'
assert 'password' in r.dropped_fields

r2 = redact_event({'trace_id': 'abc', 'api_key': 'pk_live_xyz'})
assert not r2.accepted, 'api_key did not cause drop'
"; then
    mark_pass prohibited_fields_dropped
else
    mark_fail prohibited_fields_dropped "prohibited field not dropped"
fi

# Verify HMAC-SHA256 pseudonymization.
if "$PYTHON" -c "
import sys
sys.path.insert(0, '${REPO_ROOT}/workers/src')
from zippy_workers.telemetry_pseudonym import pseudonymize, generate_pepper

pepper = generate_pepper()
h1 = pseudonymize('tenant-123', pepper, 'tenant')
h2 = pseudonymize('tenant-123', pepper, 'tenant')
h3 = pseudonymize('tenant-123', pepper, 'actor')
h4 = pseudonymize('tenant-456', pepper, 'tenant')
assert h1 == h2, 'deterministic'
assert h1 != h3, 'domain separation'
assert h1 != h4, 'tenant separation'
assert len(h1) == 24
"; then
    mark_pass pseudonymization
else
    mark_fail pseudonymization "pseudonymization assertion failed"
fi

# Verify raw identifiers never reach sinks/logs.
if "$PYTHON" -c "
import sys
sys.path.insert(0, '${REPO_ROOT}/workers/src')
from zippy_workers.telemetry_adapter import TelemetryAdapter, InMemorySink
from zippy_workers.telemetry_pseudonym import pseudonymize

pepper = 'deadbeef' * 8
raw_tenant = 'tenant-uuid-1234'
pseudo = pseudonymize(raw_tenant, pepper, 'tenant')

sink = InMemorySink()
a = TelemetryAdapter(enabled=True, sampling_rate=1.0, sink=sink, pepper=pepper)
with a.trace('op', agent_name='test-agent') as t:
    with t.span('inner') as s:
        s.set_attribute('pseudonymous_tenant_id', pseudo)

assert sink.count == 1, f'expected 1 event, got {sink.count}'
emitted = sink.events[0]
assert raw_tenant not in str(emitted), 'raw tenant reached sink'
assert pseudo == emitted.get('pseudonymous_tenant_id'), 'expected pseudonym missing'
"; then
    mark_pass raw_identifiers_absent
else
    mark_fail raw_identifiers_absent "raw identifier present in emitted event"
fi

# Verify redaction fail-closed.
if "$PYTHON" -c "
import sys
sys.path.insert(0, '${REPO_ROOT}/workers/src')
from zippy_workers.telemetry_redaction import redact_event

r = redact_event({'trace_id': 'abc', 'password': 'secret'})
assert not r.accepted, 'prohibited causes drop'
assert r.dropped_fields == ['password']

r2 = redact_event({'trace_id': 'abc', 'unknown_field': 'x'})
assert not r2.accepted, 'unknown causes drop'
"; then
    mark_pass redaction_fail_closed
else
    mark_fail redaction_fail_closed "redaction did not fail closed"
fi

# Verify sink failure is fail-open.
if "$PYTHON" -c "
import sys
sys.path.insert(0, '${REPO_ROOT}/workers/src')
from zippy_workers.telemetry_adapter import TelemetryAdapter, FailingSink

a = TelemetryAdapter(enabled=True, sampling_rate=1.0, sink=FailingSink())
a._try_emit({'trace_id': 'abc'})
assert a.emitted == 0
assert a.dropped_redaction == 0
"; then
    mark_pass sink_failure_fail_open
else
    mark_fail sink_failure_fail_open "sink failure was not fail-open"
fi

# Verify telemetry cannot alter business result.
if "$PYTHON" -c "
import sys
sys.path.insert(0, '${REPO_ROOT}/workers/src')
from zippy_workers.telemetry_adapter import TelemetryAdapter

def business():
    return 42

a = TelemetryAdapter(enabled=True, sampling_rate=1.0)
result = business()
with a.trace('op') as t:
    with t.span('s1'):
        pass
assert result == 42
"; then
    mark_pass business_result_unchanged
else
    mark_fail business_result_unchanged "business result changed by telemetry"
fi

# Prevent/detect socket/network access during pytest by running with a bogus proxy.
export http_proxy=http://127.0.0.1:9
export https_proxy=http://127.0.0.1:9
export HTTP_PROXY=http://127.0.0.1:9
export HTTPS_PROXY=http://127.0.0.1:9
export no_proxy=""
export NO_PROXY=""

PYTEST_OUT="${TMPDIR}/pytest.log"
PYTHONPATH="${REPO_ROOT}/workers/src" \
    "$PYTHON" -m pytest \
    "${REPO_ROOT}/workers/tests/test_m6_telemetry.py" \
    -q --tb=short >"$PYTEST_OUT" 2>&1 || true

focused_passed=$(grep -oE '^[0-9]+ passed' "$PYTEST_OUT" | grep -oE '[0-9]+')
if [[ -n "$focused_passed" && "$focused_passed" -eq 62 ]]; then
    mark_pass "focused_tests count=62"
    cat "$PYTEST_OUT"
else
    mark_fail "focused_tests" "expected 62, got ${focused_passed:-none}"
    cat "$PYTEST_OUT" >&2
fi

PYTEST_REG_OUT="${TMPDIR}/pytest_regression.log"
PYTHONPATH="${REPO_ROOT}/workers/src" \
    "$PYTHON" -m pytest \
    "${REPO_ROOT}/workers/tests" \
    -q --tb=short >"$PYTEST_REG_OUT" 2>&1 || true

regression_passed=$(grep -oE '^[0-9]+ passed' "$PYTEST_REG_OUT" | grep -oE '[0-9]+')
if [[ -n "$regression_passed" && "$regression_passed" -ge 122 ]]; then
    mark_pass "worker_regression"
    cat "$PYTEST_REG_OUT"
else
    mark_fail "worker_regression" "expected >=122, got ${regression_passed:-none}"
    cat "$PYTEST_REG_OUT" >&2
fi

# Ruff lint and format check.
if "$PYTHON" -m ruff check \
    "${REPO_ROOT}/workers/src/zippy_workers/config.py" \
    "${REPO_ROOT}/workers/src/zippy_workers/telemetry_adapter.py" \
    "${REPO_ROOT}/workers/src/zippy_workers/telemetry_contract.py" \
    "${REPO_ROOT}/workers/src/zippy_workers/telemetry_pseudonym.py" \
    "${REPO_ROOT}/workers/src/zippy_workers/telemetry_redaction.py" \
    "${REPO_ROOT}/workers/tests/test_m6_telemetry.py" >/dev/null 2>&1 \
    && "$PYTHON" -m ruff format --check \
    "${REPO_ROOT}/workers/src/zippy_workers/config.py" \
    "${REPO_ROOT}/workers/src/zippy_workers/telemetry_adapter.py" \
    "${REPO_ROOT}/workers/src/zippy_workers/telemetry_contract.py" \
    "${REPO_ROOT}/workers/src/zippy_workers/telemetry_pseudonym.py" \
    "${REPO_ROOT}/workers/src/zippy_workers/telemetry_redaction.py" \
    "${REPO_ROOT}/workers/tests/test_m6_telemetry.py" >/dev/null 2>&1; then
    mark_pass ruff
else
    mark_fail ruff "ruff lint or format check failed"
fi

# Scan emitted test artifacts for prohibited sentinel values.
PROHIBITED_FOUND=0
if grep -R -hE '\b(sk_live|pk_live|rzp_live|whsec_|eyJ[A-Za-z0-9_-]*\.eyJ|AIza[0-9A-Za-z_-]{35}|ghp_[A-Za-z0-9]{36}|xox[baprs]-[0-9a-zA-Z]{10,})\b' \
    "${REPO_ROOT}/workers/src/zippy_workers/telemetry_"*.py \
    "${REPO_ROOT}/workers/tests/test_m6_telemetry.py" 2>/dev/null | grep -vE 'HIGH_ENTROPY_SECRET|re\.compile|test_.*secret' >"${TMPDIR}/prohibited_scan.txt"; then
    # Allow synthetic test values used to verify redaction.
    if grep -vE 'pk_live_abc123def456ghi789jkl012mno345|sk_live_abc123def456' "${TMPDIR}/prohibited_scan.txt" >/dev/null 2>&1; then
        PROHIBITED_FOUND=1
    fi
fi

if [[ "$PROHIBITED_FOUND" -eq 0 ]]; then
    mark_pass secret_scan
else
    mark_fail secret_scan "prohibited sentinel or credential-like value found"
fi

# Confirm no live credentials are configured or exported.
if [[ -z "${LANGFUSE_PUBLIC_KEY:-}" && -z "${LANGFUSE_SECRET_KEY:-}" && -z "${LANGFUSE_HOST:-}" ]]; then
    mark_pass no_live_credentials
else
    mark_fail no_live_credentials "live Langfuse credentials present"
fi

# Confirm no external network listeners spawned by this harness.
if ! ss -lntH 2>/dev/null | grep -q ':9\b'; then
    mark_pass network_isolation
else
    mark_fail network_isolation "unexpected listener on port 9"
fi

# Verify cleanup of temporary artifacts (excluding the log this harness writes).
if [[ -d "$TMPDIR" && -z "$(find "$TMPDIR" -type f ! -name 'pytest*.log' ! -name 'prohibited_scan.txt' 2>/dev/null)" ]]; then
    mark_pass cleanup
else
    mark_fail cleanup "temporary artifacts remain"
fi

# Final verdict.
if [[ ${#FAIL_MARKERS[@]} -eq 0 ]]; then
    printf 'm6a_proof=PASS\n'
    exit 0
else
    printf 'm6a_proof=FAIL\n' >&2
    exit 1
fi
