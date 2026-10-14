"""M5-B envelope signer unit tests."""

from __future__ import annotations

import base64
import json
from uuid import UUID

import pytest

from api.services.paperclip_envelope import EnvelopeError, EnvelopeSigner

TENANT = UUID("10000000-0000-0000-0000-000000000001")
AGENT = UUID("20000000-0000-0000-0000-000000000001")
POLICY = UUID("30000000-0000-0000-0000-000000000001")
PROPOSAL = UUID("40000000-0000-0000-0000-000000000001")
GRANT = UUID("50000000-0000-0000-0000-000000000001")
KEY = b"test-signing-key-thirty-two-characters"


def _issue(purpose: str) -> str:
    signer = EnvelopeSigner(KEY)
    envelope = signer.issue(
        tenant_id=TENANT,
        subject="agent-test",
        agent_id=AGENT,
        policy_id=POLICY,
        proposal_id=PROPOSAL,
        grant_id=GRANT,
        action="UPDATE_ORDER_STATUS",
        target_system="ZIPPY",
        entity_type="order",
        entity_id="ord-123",
        payload_hash="a" * 64,
        purpose=purpose,
        ttl_seconds=300,
    )
    return base64.urlsafe_b64encode(
        json.dumps(envelope.to_dict(), separators=(",", ":"), sort_keys=True).encode("utf-8")
    ).rstrip(b"=").decode("ascii")


def test_signing_key_must_be_at_least_32_bytes():
    with pytest.raises(EnvelopeError):
        EnvelopeSigner(b"short")


def test_issue_and_verify_grant_envelope():
    signer = EnvelopeSigner(KEY)
    envelope = signer.issue(
        tenant_id=TENANT,
        subject="agent-test",
        agent_id=AGENT,
        policy_id=POLICY,
        proposal_id=PROPOSAL,
        grant_id=GRANT,
        action="UPDATE_ORDER_STATUS",
        target_system="ZIPPY",
        entity_type="order",
        entity_id="ord-123",
        payload_hash="a" * 64,
        purpose=EnvelopeSigner.PURPOSE_GRANT,
        ttl_seconds=300,
    )
    verified = signer.verify(envelope)
    assert verified.grant_id == GRANT
    assert verified.purpose == EnvelopeSigner.PURPOSE_GRANT


def test_signature_tampering_fails():
    signer = EnvelopeSigner(KEY)
    envelope = signer.issue(
        tenant_id=TENANT,
        subject="agent-test",
        agent_id=AGENT,
        policy_id=POLICY,
        proposal_id=PROPOSAL,
        grant_id=GRANT,
        action="UPDATE_ORDER_STATUS",
        target_system="ZIPPY",
        entity_type="order",
        entity_id="ord-123",
        payload_hash="a" * 64,
        purpose=EnvelopeSigner.PURPOSE_GRANT,
        ttl_seconds=300,
    )
    from api.services.paperclip_envelope import SignedEnvelope
    data = envelope.to_dict()
    data["sig"] = "A" * len(data["sig"])
    bad_envelope = SignedEnvelope.from_dict(data)
    with pytest.raises(EnvelopeError):
        signer.verify(bad_envelope)


def test_wrong_purpose_fails():
    b64 = _issue(EnvelopeSigner.PURPOSE_PROPOSAL)
    signer = EnvelopeSigner(KEY)
    with pytest.raises(EnvelopeError):
        signer.verify_string(b64, purpose=EnvelopeSigner.PURPOSE_GRANT)


def test_wrong_subject_fails():
    b64 = _issue(EnvelopeSigner.PURPOSE_GRANT)
    signer = EnvelopeSigner(KEY)
    with pytest.raises(EnvelopeError):
        signer.verify_string(b64, purpose=EnvelopeSigner.PURPOSE_GRANT, subject="other")


def test_wrong_tenant_fails():
    b64 = _issue(EnvelopeSigner.PURPOSE_GRANT)
    signer = EnvelopeSigner(KEY)
    with pytest.raises(EnvelopeError):
        signer.verify_string(b64, purpose=EnvelopeSigner.PURPOSE_GRANT, tenant_id=UUID("99999999-9999-9999-9999-999999999999"))


def test_malformed_envelope_rejected():
    signer = EnvelopeSigner(KEY)
    with pytest.raises(EnvelopeError):
        signer.verify_string("not-base64-json")


@pytest.mark.parametrize("offset,lifetime", [(0, 301), (0, 0), (301, 300), (-600, 300)])
def test_even_authentic_invalid_lifetime_is_denied(offset, lifetime):
    import time
    from dataclasses import replace

    signer = EnvelopeSigner(KEY)
    valid = signer.verify_string(_issue(EnvelopeSigner.PURPOSE_GRANT))
    start = int(time.time()) + offset
    altered = replace(valid, issued_at=start, expires_at=start + lifetime)
    altered = replace(altered, signature=signer._sign(altered))
    with pytest.raises(EnvelopeError):
        signer.verify(altered)
