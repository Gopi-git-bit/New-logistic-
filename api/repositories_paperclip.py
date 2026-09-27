"""M5-B Paperclip governance repository.

Invokes only the twelve D-28 privileged functions. No direct table access.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from psycopg import Connection, Error
from psycopg.types.json import Jsonb

from .database import PaperclipDatabase


class GovernanceError(Exception):
    pass


class GovernanceDenied(GovernanceError):
    pass


@dataclass(frozen=True)
class GovernanceResult:
    allowed: bool
    reason_code: str
    governance_id: UUID | None


class PaperclipRepository:
    def __init__(self, database: PaperclipDatabase) -> None:
        self._database = database

    @contextmanager
    def _call(
        self, tenant_id: UUID
    ) -> Iterator[Connection[dict[str, Any]]]:
        try:
            with self._database.transaction(tenant_id) as connection:
                yield connection
        except Error:
            raise GovernanceDenied("GOVERNANCE_DATABASE_UNAVAILABLE") from None

    @staticmethod
    def _to_result(row: dict[str, Any] | None) -> GovernanceResult:
        if not isinstance(row, dict) or set(row) != {"allowed", "reason_code", "governance_id"}:
            raise GovernanceDenied("GOVERNANCE_RESULT_MISSING")
        allowed, reason, identifier = row["allowed"], row["reason_code"], row["governance_id"]
        successes = {
            "PROPOSAL_EXISTS", "PROPOSAL_CREATED", "DECISION_LOCK_ACQUIRED",
            "DECISION_LOCK_RELEASED", "APPROVED", "REJECTED", "GRANT_ISSUED",
            "GRANT_REVOKED", "GRANT_CONSUMED", "EXECUTION_ATTEMPT_DUPLICATE",
            "EXECUTION_ATTEMPT_RECORDED", "HEARTBEAT_DUPLICATE", "HEARTBEAT_RECORDED",
            "TOKEN_COST_RECORDED", "LOOP_GUARD_CLEAR",
        }
        denials = {
            "AGENT_INACTIVE", "POLICY_INACTIVE_OR_CHECKSUM_MISMATCH", "LOOP_GUARD_TRIGGERED",
            "PROPOSAL_NOT_FOUND", "DECISION_LOCK_ACTIVE", "DECISION_LOCK_NOT_HELD",
            "DECISION_ALREADY_RECORDED", "SELF_APPROVAL_DENIED", "GRANT_ALREADY_ISSUED",
            "INVARIANT_FAILED", "AGENT_INACTIVE_OR_BUDGET_EXHAUSTED",
            "APPROVAL_MISSING_REJECTED_OR_EXPIRED", "GRANT_REVOCATION_INVALID",
            "EXECUTION_ATTEMPT_MISMATCH", "GRANT_CONSUMPTION_DENIED", "HEARTBEAT_DENIED",
            "AGENT_NOT_FOUND", "BUDGET_EXCEEDED",
        }
        if type(allowed) is not bool or reason not in (successes if allowed else denials):
            raise GovernanceDenied("GOVERNANCE_RESULT_UNKNOWN")
        try:
            identifier = UUID(str(identifier)) if identifier is not None else None
        except (ValueError, TypeError):
            raise GovernanceDenied("GOVERNANCE_RESULT_INVALID") from None
        if allowed and identifier is None and reason not in {"EXECUTION_ATTEMPT_DUPLICATE", "HEARTBEAT_DUPLICATE"}:
            raise GovernanceDenied("GOVERNANCE_RESULT_INVALID")
        return GovernanceResult(allowed, reason, identifier)

    def create_proposal(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        policy_id: UUID,
        action_key: str,
        target_system: str,
        entity_type: str,
        entity_id: str,
        payload: dict[str, Any],
        idempotency_key: str,
        expires_at: datetime,
    ) -> GovernanceResult:
        with self._call(tenant_id) as connection:
            row = connection.execute(
                """
                SELECT * FROM paperclip.create_proposal(
                    %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s
                )
                """,
                (
                    str(agent_id),
                    str(policy_id),
                    action_key,
                    target_system,
                    entity_type,
                    entity_id,
                    Jsonb(payload),
                    idempotency_key,
                    expires_at,
                ),
            ).fetchone()
        return self._to_result(row)

    def record_invariant(
        self,
        tenant_id: UUID,
        proposal_id: UUID,
        invariant_code: str,
        passed: bool,
    ) -> None:
        with self._call(tenant_id) as connection:
            connection.execute(
                "SELECT * FROM paperclip.record_invariant(%s, %s, %s)",
                (str(proposal_id), invariant_code, passed),
            )

    def acquire_decision_lock(
        self,
        tenant_id: UUID,
        proposal_id: UUID,
        holder_ref: str,
        reason: str,
    ) -> GovernanceResult:
        with self._call(tenant_id) as connection:
            row = connection.execute(
                "SELECT * FROM paperclip.acquire_decision_lock(%s, %s, %s)",
                (str(proposal_id), holder_ref, reason),
            ).fetchone()
        return self._to_result(row)

    def release_decision_lock(
        self,
        tenant_id: UUID,
        proposal_id: UUID,
        holder_ref: str,
    ) -> GovernanceResult:
        with self._call(tenant_id) as connection:
            row = connection.execute(
                "SELECT * FROM paperclip.release_decision_lock(%s, %s)",
                (str(proposal_id), holder_ref),
            ).fetchone()
        return self._to_result(row)

    def decide(
        self,
        tenant_id: UUID,
        proposal_id: UUID,
        approver_ref: str,
        approved: bool,
        expires_at: datetime,
    ) -> GovernanceResult:
        with self._call(tenant_id) as connection:
            row = connection.execute(
                "SELECT * FROM paperclip.decide(%s, %s, %s, %s)",
                (str(proposal_id), approver_ref, approved, expires_at),
            ).fetchone()
        return self._to_result(row)

    def issue_grant(
        self,
        tenant_id: UUID,
        proposal_id: UUID,
    ) -> GovernanceResult:
        with self._call(tenant_id) as connection:
            row = connection.execute(
                "SELECT * FROM paperclip.issue_grant(%s)",
                (str(proposal_id),),
            ).fetchone()
        return self._to_result(row)

    def revoke_grant(
        self,
        tenant_id: UUID,
        grant_id: UUID,
        actor_ref: str,
        reason: str,
    ) -> GovernanceResult:
        with self._call(tenant_id) as connection:
            row = connection.execute(
                "SELECT * FROM paperclip.revoke_grant(%s, %s, %s)",
                (str(grant_id), actor_ref, reason),
            ).fetchone()
        return self._to_result(row)

    def consume_grant(
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
        with self._call(tenant_id) as connection:
            row = connection.execute(
                """
                SELECT * FROM paperclip.consume_grant(
                    %s, %s, %s, %s, %s, %s, %s
                )
                """,
                (
                    str(grant_id),
                    str(agent_id),
                    action_key,
                    target_system,
                    entity_type,
                    entity_id,
                    payload_hash,
                ),
            ).fetchone()
        return self._to_result(row)

    def record_execution_attempt(
        self,
        tenant_id: UUID,
        grant_id: UUID,
        agent_id: UUID,
        action_key: str,
        target_system: str,
        entity_type: str,
        entity_id: str,
        request_fingerprint: str,
        status: str,
    ) -> GovernanceResult:
        with self._call(tenant_id) as connection:
            row = connection.execute(
                """
                SELECT * FROM paperclip.record_execution_attempt(
                    %s, %s, %s, %s, %s, %s, %s, %s
                )
                """,
                (
                    str(grant_id),
                    str(agent_id),
                    action_key,
                    target_system,
                    entity_type,
                    entity_id,
                    request_fingerprint,
                    status,
                ),
            ).fetchone()
        return self._to_result(row)

    def record_heartbeat(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        task_id: UUID | None,
        run_key: str,
    ) -> GovernanceResult:
        with self._call(tenant_id) as connection:
            row = connection.execute(
                "SELECT * FROM paperclip.record_heartbeat(%s, %s, %s)",
                (str(agent_id), str(task_id) if task_id else None, run_key),
            ).fetchone()
        return self._to_result(row)

    def record_token_cost(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        heartbeat_id: UUID | None,
        cost_usd: Decimal,
    ) -> GovernanceResult:
        with self._call(tenant_id) as connection:
            row = connection.execute(
                "SELECT * FROM paperclip.record_token_cost(%s, %s, %s)",
                (str(agent_id), str(heartbeat_id) if heartbeat_id else None, cost_usd),
            ).fetchone()
        return self._to_result(row)

    def evaluate_loop_guard(
        self,
        tenant_id: UUID,
        proposal_id: UUID,
    ) -> GovernanceResult:
        with self._call(tenant_id) as connection:
            row = connection.execute(
                "SELECT * FROM paperclip.evaluate_loop_guard(%s)",
                (str(proposal_id),),
            ).fetchone()
        return self._to_result(row)
