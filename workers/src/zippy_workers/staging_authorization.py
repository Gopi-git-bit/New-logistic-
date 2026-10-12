"""Endpoint-bound staging checks; no real grants are registered or loaded.

Only a future reviewed authority integration may supply approved grants. Request
arguments, key presence and evidence reference strings cannot approve a grant.
This module is not authentication or a sandbox for hostile in-process Python.
"""

from __future__ import annotations

import hashlib
import math
import os
import re
import stat
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import MappingProxyType
from typing import Never

from .capabilities import UnauthorizedCapability
from .recommendation_provider import ProviderRequestProfile, ProviderSettings


def _deny(reason: str) -> Never:
    raise UnauthorizedCapability(f"OMS_STAGING_{reason}")


def source_digest() -> str:
    """Bind a reviewed permit to the actual local adapter/runner source bytes."""
    root = Path(__file__).resolve().parents[2]
    names = (
        "src/zippy_workers/capabilities.py",
        "src/zippy_workers/recommendations.py",
        "src/zippy_workers/recommendation_provider.py",
        "src/zippy_workers/staging_authorization.py",
        "scripts/run_oms_recommendation.py",
    )
    digest = hashlib.sha256()
    for name in names:
        path = root / name
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 1_048_576:
            _deny("SOURCE_UNVERIFIED")
        data = path.read_bytes()
        digest.update(name.encode() + b"\0" + len(data).to_bytes(8, "big") + data)
    return digest.hexdigest()


@dataclass(frozen=True)
class StagingInvocation:
    """Non-secret invocation identity; SHA alone is not artifact attestation."""

    source_sha: str
    source_digest: str
    uid: int
    credential_file: Path | None


@dataclass(frozen=True)
class ApprovedStagingGrant:
    """Trusted-authority record, never parsed from CLI or environment input."""

    grant_id: str
    agent: str
    operation: str
    endpoint: str
    model: str
    profile: ProviderRequestProfile
    source_sha: str
    source_digest: str
    uid: int
    credential_file: Path
    claim_directory: Path
    not_before: datetime
    expires_at: datetime
    timeout_seconds: float
    max_output_tokens: int
    max_requests: int
    spend_ceiling_usd: Decimal
    budget_evidence_ref: str
    credential_evidence_ref: str
    isolation_evidence_ref: str
    approver_ref: str


class ExclusiveGrantClaims:
    """Consume one approved invocation durably, before creating an HTTP client.

    The pre-existing private state directory belongs only to the isolated target.
    A claim is never removed on failure. Repeating a failed run requires a new
    independently approved grant; this is not a provider idempotency guarantee.
    """

    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def consume(self, grant_id: str) -> None:
        if re.fullmatch(r"[a-z0-9-]{1,64}", grant_id) is None:
            _deny("GRANT_INVALID")
        directory_fd = -1
        try:
            directory_fd = os.open(self.directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            info = os.fstat(directory_fd)
            if info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o700:
                _deny("CLAIM_STORE_UNSAFE")
            file_fd = os.open(
                f"{grant_id}.consumed",
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o600,
                dir_fd=directory_fd,
            )
            try:
                os.fsync(file_fd)
                os.fsync(directory_fd)
            finally:
                os.close(file_fd)
        except FileExistsError:
            _deny("GRANT_ALREADY_USED")
        except OSError:
            _deny("CLAIM_STORE_UNAVAILABLE")
        finally:
            if directory_fd >= 0:
                os.close(directory_fd)


# Intentionally empty. No CLI flag, credential file or environment variable can
# populate this registry. A signed/authenticated issuer integration is deferred.
APPROVED_STAGING_GRANTS: Mapping[str, ApprovedStagingGrant] = MappingProxyType({})


def validate_and_consume_grant(
    settings: ProviderSettings,
    profile: ProviderRequestProfile | None,
    invocation: StagingInvocation,
    grant: ApprovedStagingGrant,
    claims: ExclusiveGrantClaims,
    *,
    now: datetime,
) -> None:
    """Validate a trusted grant and atomically reserve its sole invocation."""
    if profile is not ProviderRequestProfile.DEEPSEEK_DIRECT:
        _deny("PROFILE_REQUIRED")
    profile.validate_settings(settings)
    if (
        grant.agent != "order_management"
        or grant.operation != "recommend_drivers"
        or grant.profile is not profile
        or grant.endpoint != settings.endpoint
        or grant.model != settings.model
        or grant.source_sha != invocation.source_sha
        or grant.source_digest != invocation.source_digest
        or re.fullmatch(r"[0-9a-f]{40}", invocation.source_sha) is None
        or re.fullmatch(r"[0-9a-f]{64}", invocation.source_digest) is None
        or type(invocation.uid) is not int
        or invocation.uid <= 0
        or grant.uid != invocation.uid
        or invocation.credential_file is None
        or grant.credential_file.resolve() != invocation.credential_file.resolve()
        or grant.claim_directory.resolve() != claims.directory.resolve()
    ):
        _deny("GRANT_BINDING_MISMATCH")
    if (
        any(not isinstance(value, datetime) for value in (now, grant.not_before, grant.expires_at))
        or any(
            value.tzinfo is None or value.utcoffset() is None
            for value in (now, grant.not_before, grant.expires_at)
        )
        or not grant.not_before <= now < grant.expires_at
        or not grant.not_before < grant.expires_at
    ):
        _deny("GRANT_EXPIRED_OR_NOT_ACTIVE")
    if (
        type(grant.max_requests) is not int
        or grant.max_requests != 1
        or type(grant.max_output_tokens) is not int
        or grant.max_output_tokens != settings.max_output_tokens
        or type(grant.timeout_seconds) not in (int, float)
        or not math.isfinite(grant.timeout_seconds)
        or grant.timeout_seconds != settings.timeout_seconds
    ):
        _deny("GRANT_LIMIT_MISMATCH")
    if (
        not isinstance(grant.spend_ceiling_usd, Decimal)
        or not grant.spend_ceiling_usd.is_finite()
        or grant.spend_ceiling_usd <= 0
        or any(
            not isinstance(ref, str)
            or not ref.strip()
            or ref.strip().lower() in {"unknown", "pending", "unverified"}
            for ref in (
                grant.budget_evidence_ref,
                grant.credential_evidence_ref,
                grant.isolation_evidence_ref,
                grant.approver_ref,
            )
        )
    ):
        _deny("GRANT_EVIDENCE_MISSING")
    ensure_execution_window(grant.expires_at, settings.timeout_seconds, now=now)
    claims.consume(grant.grant_id)


def ensure_execution_window(
    expires_at: datetime, timeout_seconds: float, *, now: datetime | None = None
) -> None:
    """Require the full bounded run to fit before expiry, also after claim I/O."""
    current = datetime.now(UTC) if now is None else now
    if current + timedelta(seconds=timeout_seconds) > expires_at:
        _deny("GRANT_WINDOW_TOO_SHORT")


def assert_staging_authorized(
    settings: ProviderSettings,
    profile: ProviderRequestProfile | None,
    *,
    source_sha: str | None,
    approval_id: str | None,
    claim_directory: Path | None,
    credential_file: Path | None,
) -> datetime:
    """Resolve only trusted registered authority; current runtime always denies."""
    grant = APPROVED_STAGING_GRANTS.get(approval_id or "")
    if grant is None:
        _deny("ENDPOINT_GRANT_NOT_AUTHORIZED")
    if source_sha is None or claim_directory is None:
        _deny("GRANT_BINDING_MISSING")
    validate_and_consume_grant(
        settings,
        profile,
        StagingInvocation(source_sha, source_digest(), os.geteuid(), credential_file),
        grant,
        ExclusiveGrantClaims(claim_directory),
        now=datetime.now(UTC),
    )
    return grant.expires_at
