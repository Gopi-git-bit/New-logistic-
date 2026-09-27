"""M5-B synthetic/disposable executor adapter.

Performs no Zippy, Odoo, Razorpay, payment, filesystem, network or external
operation. It consumes a server-signed grant envelope and records a synthetic
execution attempt. The database grant remains the sole authority.
"""

from __future__ import annotations

import hashlib
from uuid import UUID

from api.repositories_paperclip import (
    GovernanceDenied,
    GovernanceResult,
    PaperclipRepository,
)


class SyntheticExecutor:
    """Fake executor for disposable M5-B validation."""

    def __init__(self, repository: PaperclipRepository) -> None:
        self._repository = repository

    def execute(
        self,
        tenant_id: UUID,
        grant_id: UUID,
        agent_id: UUID,
        action_key: str,
        target_system: str,
        entity_type: str,
        entity_id: str,
        payload_hash: str,
    ) -> GovernanceResult:
        """Atomically consume once, then record a synthetic completion; fail closed."""
        consume = self._repository.consume_grant(
            tenant_id,
            grant_id,
            agent_id,
            action_key,
            target_system,
            entity_type,
            entity_id,
            payload_hash,
        )
        if not consume.allowed:
            raise GovernanceDenied(consume.reason_code)
        attempt = self._repository.record_execution_attempt(
            tenant_id,
            grant_id,
            agent_id,
            action_key,
            target_system,
            entity_type,
            entity_id,
            hashlib.sha256((str(grant_id) + ":synthetic-complete:" + payload_hash).encode()).hexdigest(),
            "SUCCEEDED",
        )
        if not attempt.allowed:
            raise GovernanceDenied(attempt.reason_code)
        return GovernanceResult(
            allowed=True,
            reason_code="SYNTHETIC_EXECUTION_RECORDED",
            governance_id=grant_id,
        )
