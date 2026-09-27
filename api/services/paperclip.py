"""M5-B Paperclip governance service layer.

Coordinates authentication, authorization, server-signed envelopes, and the
synthetic executor over the twelve D-28 privileged Paperclip functions.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from api.auth import AuthenticatedSubject
from api.config import Settings
from api.repositories import ForbiddenError, RequestIdentity
from api.repositories_paperclip import (
    GovernanceDenied,
    GovernanceResult,
    PaperclipRepository,
)
from api.services.paperclip_envelope import (
    EnvelopeSigner,
    SignedEnvelope,
)
from api.services.synthetic_executor import SyntheticExecutor


class PaperclipServiceError(Exception):
    pass


class PaperclipService:
    """Authenticated facade for the Paperclip governance boundary."""

    def __init__(
        self,
        repository: PaperclipRepository,
        signer: EnvelopeSigner,
        executor: SyntheticExecutor,
        settings: Settings,
    ) -> None:
        if (not settings.paperclip_owner_subject or not settings.paperclip_executor_subject
                or settings.paperclip_policy_id is None
                or settings.paperclip_owner_subject == settings.paperclip_executor_subject
                or settings.paperclip_owner_subject in settings.paperclip_agent_bindings
                or settings.paperclip_executor_subject in settings.paperclip_agent_bindings):
            raise GovernanceDenied("GOVERNANCE_CONFIGURATION_INVALID")
        self._repository = repository
        self._signer = signer
        self._executor = executor
        self._settings = settings

    def _resolve_agent(self, subject: AuthenticatedSubject) -> UUID:
        agent_id = self._settings.paperclip_agent_bindings.get(
            subject.external_subject
        )
        if agent_id is None:
            raise ForbiddenError("Actor is not authorized for Paperclip governance")
        return agent_id

    @staticmethod
    def _require_admin(identity: RequestIdentity) -> None:
        if "admin" not in identity.roles:
            raise ForbiddenError("Admin role is required")

    def _require_owner(
        self, subject: AuthenticatedSubject, identity: RequestIdentity
    ) -> None:
        self._require_admin(identity)
        if subject.external_subject != self._settings.paperclip_owner_subject:
            raise ForbiddenError("Owner identity is required")

    def _require_executor(
        self, subject: AuthenticatedSubject
    ) -> None:
        if subject.external_subject != self._settings.paperclip_executor_subject:
            raise ForbiddenError("Executor identity is required")

    @staticmethod
    def _to_uuid(value: str) -> UUID:
        try:
            return UUID(value)
        except ValueError as exc:
            raise PaperclipServiceError("INVALID_UUID") from exc

    @staticmethod
    def _payload_hash(payload: dict[str, Any]) -> str:
        # PostgreSQL jsonb::text: UTF-8 byte-length key ordering and spaced separators.
        import hashlib
        import json
        import math

        def encode(value: Any) -> str:
            if isinstance(value, dict):
                if any(not isinstance(key, str) for key in value):
                    raise GovernanceDenied("PAYLOAD_INVALID")
                keys = sorted(value, key=lambda key: (len(key.encode("utf-8")), key.encode("utf-8")))
                return "{" + ", ".join(encode(key) + ": " + encode(value[key]) for key in keys) + "}"
            if isinstance(value, list):
                return "[" + ", ".join(encode(item) for item in value) + "]"
            if isinstance(value, float):
                if not math.isfinite(value):
                    raise GovernanceDenied("PAYLOAD_INVALID")
                return format(Decimal(str(value)), "f")
            if value is None or type(value) in (str, int, bool):
                return json.dumps(value, ensure_ascii=False, allow_nan=False)
            raise GovernanceDenied("PAYLOAD_INVALID")

        return hashlib.sha256(encode(payload).encode("utf-8")).hexdigest()

    def create_proposal(
        self,
        subject: AuthenticatedSubject,
        action_key: str,
        target_system: str,
        entity_type: str,
        entity_id: str,
        payload: dict[str, Any],
        idempotency_key: str,
        expires_at: datetime,
        correlation_id: UUID,
    ) -> GovernanceResult:
        agent_id = self._resolve_agent(subject)
        result = self._repository.create_proposal(
            tenant_id=self._settings.platform_id,
            agent_id=agent_id,
            policy_id=self._settings.paperclip_policy_id,
            action_key=action_key,
            target_system=target_system,
            entity_type=entity_type,
            entity_id=entity_id,
            payload=payload,
            idempotency_key=idempotency_key,
            expires_at=expires_at,
        )
        return result

    def issue_proposal_envelope(
        self,
        subject: AuthenticatedSubject,
        proposal_id: UUID,
        action_key: str,
        target_system: str,
        entity_type: str,
        entity_id: str,
        payload: dict[str, Any],
    ) -> SignedEnvelope:
        agent_id = self._resolve_agent(subject)
        return self._signer.issue(
            tenant_id=self._settings.platform_id,
            subject=subject.external_subject,
            agent_id=agent_id,
            policy_id=self._settings.paperclip_policy_id,
            proposal_id=proposal_id,
            grant_id=None,
            action=action_key,
            target_system=target_system,
            entity_type=entity_type,
            entity_id=entity_id,
            payload_hash=self._payload_hash(payload),
            purpose=EnvelopeSigner.PURPOSE_PROPOSAL,
            ttl_seconds=self._settings.paperclip_envelope_ttl_seconds,
        )

    def record_invariant(
        self,
        subject: AuthenticatedSubject,
        identity: RequestIdentity,
        proposal_id: UUID,
        invariant_code: str,
        passed: bool,
    ) -> None:
        self._require_admin(identity)
        self._repository.record_invariant(
            tenant_id=self._settings.platform_id,
            proposal_id=proposal_id,
            invariant_code=invariant_code,
            passed=passed,
        )

    def acquire_decision_lock(
        self,
        subject: AuthenticatedSubject,
        identity: RequestIdentity,
        proposal_id: UUID,
        reason: str,
    ) -> GovernanceResult:
        self._require_admin(identity)
        return self._repository.acquire_decision_lock(
            tenant_id=self._settings.platform_id,
            proposal_id=proposal_id,
            holder_ref=subject.external_subject,
            reason=reason,
        )

    def release_decision_lock(
        self,
        subject: AuthenticatedSubject,
        identity: RequestIdentity,
        proposal_id: UUID,
    ) -> GovernanceResult:
        self._require_admin(identity)
        return self._repository.release_decision_lock(
            tenant_id=self._settings.platform_id,
            proposal_id=proposal_id,
            holder_ref=subject.external_subject,
        )

    def decide(
        self,
        subject: AuthenticatedSubject,
        identity: RequestIdentity,
        proposal_id: UUID,
        approved: bool,
        expires_at: datetime,
    ) -> GovernanceResult:
        self._require_owner(subject, identity)
        return self._repository.decide(
            tenant_id=self._settings.platform_id,
            proposal_id=proposal_id,
            approver_ref=subject.external_subject,
            approved=approved,
            expires_at=expires_at,
        )

    def issue_grant(
        self,
        subject: AuthenticatedSubject,
        identity: RequestIdentity,
        proposal_id: UUID,
    ) -> GovernanceResult:
        self._require_admin(identity)
        return self._repository.issue_grant(
            tenant_id=self._settings.platform_id,
            proposal_id=proposal_id,
        )

    def issue_grant_envelope(
        self,
        subject: AuthenticatedSubject,
        proposal_id: UUID,
        grant_id: UUID,
        action_key: str,
        target_system: str,
        entity_type: str,
        entity_id: str,
        payload: dict[str, Any],
    ) -> SignedEnvelope:
        agent_id = self._resolve_agent(subject)
        return self._signer.issue(
            tenant_id=self._settings.platform_id,
            subject=self._settings.paperclip_executor_subject,
            agent_id=agent_id,
            policy_id=self._settings.paperclip_policy_id,
            proposal_id=proposal_id,
            grant_id=grant_id,
            action=action_key,
            target_system=target_system,
            entity_type=entity_type,
            entity_id=entity_id,
            payload_hash=self._payload_hash(payload),
            purpose=EnvelopeSigner.PURPOSE_GRANT,
            ttl_seconds=self._settings.paperclip_envelope_ttl_seconds,
        )

    def revoke_grant(
        self,
        subject: AuthenticatedSubject,
        identity: RequestIdentity,
        grant_id: UUID,
        reason: str,
    ) -> GovernanceResult:
        self._require_admin(identity)
        return self._repository.revoke_grant(
            tenant_id=self._settings.platform_id,
            grant_id=grant_id,
            actor_ref=subject.external_subject,
            reason=reason,
        )

    def consume_grant(
        self,
        subject: AuthenticatedSubject,
        envelope_b64: str,
        grant_id: UUID | None = None,
    ) -> GovernanceResult:
        self._require_executor(subject)
        envelope = self._signer.verify_string(
            envelope_b64,
            purpose=EnvelopeSigner.PURPOSE_GRANT,
            subject=subject.external_subject,
            tenant_id=self._settings.platform_id,
            grant_id=grant_id,
        )
        if envelope.policy_id != self._settings.paperclip_policy_id or envelope.agent_id not in self._settings.paperclip_agent_bindings.values():
            raise GovernanceDenied("ENVELOPE_MAPPING_MISMATCH")
        if envelope.grant_id is None:
            raise GovernanceDenied("ENVELOPE_GRANT_MISSING")
        result = self._executor.execute(
            tenant_id=envelope.tenant_id,
            grant_id=envelope.grant_id,
            agent_id=envelope.agent_id,
            action_key=envelope.action,
            target_system=envelope.target_system,
            entity_type=envelope.entity_type,
            entity_id=envelope.entity_id,
            payload_hash=envelope.payload_hash,
        )
        return result

    def record_execution_attempt(
        self,
        subject: AuthenticatedSubject,
        envelope_b64: str,
        request_fingerprint: str,
        status: str,
        grant_id: UUID | None = None,
    ) -> GovernanceResult:
        self._require_executor(subject)
        envelope = self._signer.verify_string(
            envelope_b64,
            purpose=EnvelopeSigner.PURPOSE_GRANT,
            subject=subject.external_subject,
            tenant_id=self._settings.platform_id,
            grant_id=grant_id,
        )
        if envelope.policy_id != self._settings.paperclip_policy_id or envelope.agent_id not in self._settings.paperclip_agent_bindings.values():
            raise GovernanceDenied("ENVELOPE_MAPPING_MISMATCH")
        if envelope.grant_id is None:
            raise GovernanceDenied("ENVELOPE_GRANT_MISSING")
        return self._repository.record_execution_attempt(
            tenant_id=envelope.tenant_id,
            grant_id=envelope.grant_id,
            agent_id=envelope.agent_id,
            action_key=envelope.action,
            target_system=envelope.target_system,
            entity_type=envelope.entity_type,
            entity_id=envelope.entity_id,
            request_fingerprint=request_fingerprint,
            status=status,
        )

    def record_heartbeat(
        self,
        subject: AuthenticatedSubject,
        task_id: UUID | None,
        run_key: str,
    ) -> GovernanceResult:
        agent_id = self._resolve_agent(subject)
        return self._repository.record_heartbeat(
            tenant_id=self._settings.platform_id,
            agent_id=agent_id,
            task_id=task_id,
            run_key=run_key,
        )

    def record_token_cost(
        self,
        subject: AuthenticatedSubject,
        heartbeat_id: UUID | None,
        cost_usd: Decimal,
    ) -> GovernanceResult:
        agent_id = self._resolve_agent(subject)
        return self._repository.record_token_cost(
            tenant_id=self._settings.platform_id,
            agent_id=agent_id,
            heartbeat_id=heartbeat_id,
            cost_usd=cost_usd,
        )

    def evaluate_loop_guard(
        self,
        subject: AuthenticatedSubject,
        identity: RequestIdentity,
        proposal_id: UUID,
    ) -> GovernanceResult:
        self._require_admin(identity)
        return self._repository.evaluate_loop_guard(
            tenant_id=self._settings.platform_id,
            proposal_id=proposal_id,
        )
