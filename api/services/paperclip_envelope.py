"""Server-signed governance envelope for M5-B.

The envelope binds an authenticated subject to a Paperclip agent, policy,
tenant, proposal, grant, action, target, entity and payload hash. It is
signed with an HMAC-SHA256 server secret and is valid for at most five
minutes. The envelope is not a grant: the Paperclip database grant remains
authoritative.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass
from typing import Any
from uuid import UUID


class EnvelopeError(Exception):
    pass


@dataclass(frozen=True)
class SignedEnvelope:
    version: str
    tenant_id: UUID
    subject: str
    agent_id: UUID
    policy_id: UUID
    proposal_id: UUID | None
    grant_id: UUID | None
    action: str
    target_system: str
    entity_type: str
    entity_id: str
    payload_hash: str
    purpose: str
    issued_at: int
    expires_at: int
    nonce: str
    signature: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "v": self.version,
            "t": str(self.tenant_id),
            "s": self.subject,
            "a": str(self.agent_id),
            "p": str(self.policy_id),
            "pr": str(self.proposal_id) if self.proposal_id else None,
            "g": str(self.grant_id) if self.grant_id else None,
            "ak": self.action,
            "ts": self.target_system,
            "et": self.entity_type,
            "ei": self.entity_id,
            "ph": self.payload_hash,
            "pu": self.purpose,
            "iat": self.issued_at,
            "exp": self.expires_at,
            "n": self.nonce,
            "sig": self.signature,
        }

    def to_string(self) -> str:
        raw = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":")).encode("utf-8")
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SignedEnvelope:
        try:
            return cls(
                version=data["v"],
                tenant_id=UUID(data["t"]),
                subject=data["s"],
                agent_id=UUID(data["a"]),
                policy_id=UUID(data["p"]),
                proposal_id=UUID(data["pr"]) if data.get("pr") else None,
                grant_id=UUID(data["g"]) if data.get("g") else None,
                action=data["ak"],
                target_system=data["ts"],
                entity_type=data["et"],
                entity_id=data["ei"],
                payload_hash=data["ph"],
                purpose=data["pu"],
                issued_at=int(data["iat"]),
                expires_at=int(data["exp"]),
                nonce=data["n"],
                signature=data["sig"],
            )
        except Exception as exc:
            raise EnvelopeError("ENVELOPE_MALFORMED") from exc


class EnvelopeSigner:
    """Issues and verifies short-lived governance envelopes."""

    VERSION = "m5b-v1"
    PURPOSE_PROPOSAL = "proposal"
    PURPOSE_GRANT = "grant"

    def __init__(self, signing_key: bytes, max_ttl_seconds: int = 300) -> None:
        if len(signing_key) < 32:
            raise EnvelopeError("SIGNING_KEY_TOO_SHORT")
        self._key = signing_key
        self._max_ttl = min(max(max_ttl_seconds, 1), 300)

    def _canonical_payload(self, envelope: SignedEnvelope) -> bytes:
        # Canonical JSON: sorted keys, no whitespace, UTF-8.
        data = {
            "v": envelope.version,
            "t": str(envelope.tenant_id),
            "s": envelope.subject,
            "a": str(envelope.agent_id),
            "p": str(envelope.policy_id),
            "pr": str(envelope.proposal_id) if envelope.proposal_id else None,
            "g": str(envelope.grant_id) if envelope.grant_id else None,
            "ak": envelope.action,
            "ts": envelope.target_system,
            "et": envelope.entity_type,
            "ei": envelope.entity_id,
            "ph": envelope.payload_hash,
            "pu": envelope.purpose,
            "iat": envelope.issued_at,
            "exp": envelope.expires_at,
            "n": envelope.nonce,
        }
        return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

    def _sign(self, envelope: SignedEnvelope) -> str:
        payload = self._canonical_payload(envelope)
        mac = hmac.new(self._key, payload, hashlib.sha256).digest()
        return base64.urlsafe_b64encode(mac).rstrip(b"=").decode("ascii")

    def issue(
        self,
        tenant_id: UUID,
        subject: str,
        agent_id: UUID,
        policy_id: UUID,
        proposal_id: UUID | None,
        grant_id: UUID | None,
        action: str,
        target_system: str,
        entity_type: str,
        entity_id: str,
        payload_hash: str,
        purpose: str,
        ttl_seconds: int = 300,
    ) -> SignedEnvelope:
        if purpose not in {self.PURPOSE_PROPOSAL, self.PURPOSE_GRANT}:
            raise EnvelopeError("ENVELOPE_PURPOSE_INVALID")
        ttl = min(max(ttl_seconds, 1), self._max_ttl)
        now = int(time.time())
        envelope = SignedEnvelope(
            version=self.VERSION,
            tenant_id=tenant_id,
            subject=subject,
            agent_id=agent_id,
            policy_id=policy_id,
            proposal_id=proposal_id,
            grant_id=grant_id,
            action=action,
            target_system=target_system,
            entity_type=entity_type,
            entity_id=entity_id,
            payload_hash=payload_hash,
            purpose=purpose,
            issued_at=now,
            expires_at=now + ttl,
            nonce=secrets.token_urlsafe(32),
            signature="",
        )
        signed = SignedEnvelope(
            version=envelope.version,
            tenant_id=envelope.tenant_id,
            subject=envelope.subject,
            agent_id=envelope.agent_id,
            policy_id=envelope.policy_id,
            proposal_id=envelope.proposal_id,
            grant_id=envelope.grant_id,
            action=envelope.action,
            target_system=envelope.target_system,
            entity_type=envelope.entity_type,
            entity_id=envelope.entity_id,
            payload_hash=envelope.payload_hash,
            purpose=envelope.purpose,
            issued_at=envelope.issued_at,
            expires_at=envelope.expires_at,
            nonce=envelope.nonce,
            signature=self._sign(envelope),
        )
        return signed

    def verify(
        self,
        envelope: SignedEnvelope,
        *,
        purpose: str | None = None,
        subject: str | None = None,
        tenant_id: UUID | None = None,
        agent_id: UUID | None = None,
        proposal_id: UUID | None = None,
        grant_id: UUID | None = None,
    ) -> SignedEnvelope:
        if envelope.version != self.VERSION:
            raise EnvelopeError("ENVELOPE_VERSION_MISMATCH")
        expected = self._sign(envelope)
        if not hmac.compare_digest(expected, envelope.signature):
            raise EnvelopeError("ENVELOPE_SIGNATURE_INVALID")
        now = int(time.time())
        if not 0 < envelope.expires_at - envelope.issued_at <= self._max_ttl or envelope.issued_at > now:
            raise EnvelopeError("ENVELOPE_LIFETIME_INVALID")
        if envelope.expires_at <= now:
            raise EnvelopeError("ENVELOPE_EXPIRED")
        if purpose is not None and envelope.purpose != purpose:
            raise EnvelopeError("ENVELOPE_PURPOSE_MISMATCH")
        if subject is not None and envelope.subject != subject:
            raise EnvelopeError("ENVELOPE_SUBJECT_MISMATCH")
        if tenant_id is not None and envelope.tenant_id != tenant_id:
            raise EnvelopeError("ENVELOPE_TENANT_MISMATCH")
        if agent_id is not None and envelope.agent_id != agent_id:
            raise EnvelopeError("ENVELOPE_AGENT_MISMATCH")
        if proposal_id is not None and envelope.proposal_id != proposal_id:
            raise EnvelopeError("ENVELOPE_PROPOSAL_MISMATCH")
        if grant_id is not None and envelope.grant_id != grant_id:
            raise EnvelopeError("ENVELOPE_GRANT_MISMATCH")
        return envelope

    def verify_string(
        self,
        envelope_b64: str,
        *,
        purpose: str | None = None,
        subject: str | None = None,
        tenant_id: UUID | None = None,
        agent_id: UUID | None = None,
        proposal_id: UUID | None = None,
        grant_id: UUID | None = None,
    ) -> SignedEnvelope:
        try:
            # Enforce strict base64 padding; reject embedded JSON blobs.
            padded = envelope_b64 + "=" * (-len(envelope_b64) % 4)
            raw = base64.urlsafe_b64decode(padded)
            data = json.loads(raw.decode("utf-8"))
        except Exception as exc:
            raise EnvelopeError("ENVELOPE_MALFORMED") from exc
        envelope = SignedEnvelope.from_dict(data)
        return self.verify(
            envelope,
            purpose=purpose,
            subject=subject,
            tenant_id=tenant_id,
            agent_id=agent_id,
            proposal_id=proposal_id,
            grant_id=grant_id,
        )
