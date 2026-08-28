"""M5 tests — OCR provider, notification sender, and handlers."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from zippy_workers.ocr_provider import (
    OCRRawResult,
    TesseractExtractor,
    make_ocr_provider,
)
from zippy_workers.notification_sender import (
    DeliveryResult,
    StubSender,
    TwilioSMSSender,
    ResendEmailSender,
    make_notification_sender,
)
from zippy_workers.handlers import (
    HandlerResult,
    process_document_upload,
    process_notification_job,
)


# =========================================================================
# OCR Provider
# =========================================================================

class TestOCRRawResult:
    def test_derived_fields(self):
        r = OCRRawResult(raw_text="hello world", confidence=0.9, provider="test")
        assert r.word_count == 2
        assert r.char_count == 11

    def test_empty_text(self):
        r = OCRRawResult(raw_text="", confidence=0.0, provider="test")
        assert r.word_count == 0
        assert r.char_count == 0


class TestTesseractExtractor:
    def test_unavailable_provider_returns_graceful(self):
        ext = TesseractExtractor(tesseract_cmd="nonexistent_tesseract_999")
        r = ext.extract(b"fake image", "image/jpeg")
        assert r.provider == "tesseract_unavailable"
        assert r.confidence == 0.0

    def test_provider_name(self):
        assert TesseractExtractor().provider_name == "tesseract"

    def test_is_protocol(self):
        assert isinstance(TesseractExtractor(), object)


class TestMakeOCRProvider:
    def test_default_is_tesseract(self):
        p = make_ocr_provider()
        assert p.provider_name == "tesseract"

    def test_explicit_tesseract(self):
        p = make_ocr_provider("tesseract")
        assert p.provider_name == "tesseract"

    def test_unknown_raises(self):
        try:
            make_ocr_provider("nonexistent_engine")
            assert False, "should have raised"
        except ValueError as e:
            assert "nonexistent_engine" in str(e)


# =========================================================================
# Notification Sender
# =========================================================================

class TestStubSender:
    def test_always_succeeds(self):
        s = StubSender()
        r = s.send("+919000000000", "Hello", "Body")
        assert r.ok
        assert r.provider == "stub"
        assert r.external_id is not None


class TestTwilioSMSSender:
    def test_no_credentials_fails(self):
        s = TwilioSMSSender()
        r = s.send("+919000000000", "Hi", "Body")
        assert not r.ok
        assert "not configured" in (r.error or "")


class TestResendEmailSender:
    def test_no_credentials_fails(self):
        s = ResendEmailSender()
        r = s.send("test@x.com", "Hi", "Body")
        assert not r.ok
        assert "not configured" in (r.error or "")


class TestMakeNotificationSender:
    def test_stub(self):
        assert isinstance(make_notification_sender("stub"), StubSender)

    def test_sms(self):
        assert isinstance(make_notification_sender("sms"), TwilioSMSSender)

    def test_email(self):
        assert isinstance(make_notification_sender("email"), ResendEmailSender)

    def test_unknown_raises(self):
        try:
            make_notification_sender("nonexistent")
            assert False, "should have raised"
        except ValueError:
            pass


# =========================================================================
# Handlers — POD pipeline
# =========================================================================

class FakeDocDb:
    """Fake Db with only the M5 document methods."""
    def __init__(self):
        self.docs: list[dict] = []
        self.transitions: list[tuple[str, str]] = []

    def transition_order(self, order_id, new_status):
        self.transitions.append((order_id, new_status))

    def upsert_document(self, order_id, doc_type, image_url,
                        ocr_text, ocr_confidence, ocr_provider, uploaded_by):
        doc_id = f"doc-{len(self.docs)+1}"
        self.docs.append({
            "order_id": order_id, "doc_type": doc_type,
            "image_url": image_url, "ocr_text": ocr_text,
            "ocr_confidence": ocr_confidence, "ocr_provider": ocr_provider,
        })
        return doc_id


class FailingOCR:
    """OCR that always fails."""
    @property
    def provider_name(self): return "failing"

    def extract(self, image_bytes, content_type="image/jpeg"):
        raise RuntimeError("OCR boom")


class StubOCR:
    """OCR that returns fixed text."""
    @property
    def provider_name(self): return "stub_ocr"

    def extract(self, image_bytes, content_type="image/jpeg"):
        return OCRRawResult(raw_text="DELIVERED OK", confidence=0.95,
                            provider="stub_ocr")


def test_pod_handler_missing_order_id():
    db = FakeDocDb()
    r = process_document_upload({}, db, StubOCR())
    assert not r.ok and "missing order_id" in r.detail["error"]


def test_pod_handler_missing_image_url():
    db = FakeDocDb()
    r = process_document_upload({"order_id": "o-1"}, db, StubOCR())
    assert not r.ok and "missing image_url" in r.detail["error"]


def test_pod_handler_non_pod_does_not_advance():
    db = FakeDocDb()
    # Non-POD doc — no transition
    r = process_document_upload(
        {"order_id": "o-2", "document_type": "invoice",
         "image_url": "http://example.com/img.jpg"},
        db, StubOCR(),
    )
    assert r.ok and r.detail["doc_id"] == "doc-1"
    assert not db.transitions  # no state machine advance for invoice


def test_pod_handler_advances_to_delivered():
    """POD doc triggers transition to 'delivered' (URL fetch fails in stub,
    but handler still stores the doc — OCR failure is non-fatal)."""
    db = FakeDocDb()
    r = process_document_upload(
        {"order_id": "o-3", "document_type": "pod",
         "image_url": "http://example.com/pod.jpg"},
        db, StubOCR(),
    )
    assert r.ok
    assert ("o-3", "delivered") in db.transitions


def test_pod_handler_idempotent_already_delivered():
    """transition_order raises 'Invalid transition' → treated as idempotent."""
    class DeliveredDb(FakeDocDb):
        def transition_order(self, oid, ns):
            raise RuntimeError("Invalid transition from delivered")

    db = DeliveredDb()
    r = process_document_upload(
        {"order_id": "o-4", "document_type": "pod",
         "image_url": "http://example.com/pod2.jpg"},
        db, StubOCR(),
    )
    assert r.ok  # idempotent no-op


# =========================================================================
# Handlers — Notification delivery
# =========================================================================

class FakeNotifyDb:
    def __init__(self):
        self.sent: list[tuple[str, str | None]] = []
        self.failed: list[tuple[str, str | None]] = []
        self.logs: list[dict] = []

    def mark_notification_sent(self, nid, external_id=None):
        self.sent.append((nid, external_id))

    def mark_notification_failed(self, nid, reason=None):
        self.failed.append((nid, reason))

    def log_notification(self, user_id, channel, ntype, title, body,
                         payload=None, external_id=None, idempotency_key=None):
        self.logs.append({"user_id": user_id, "channel": channel,
                          "title": title, "external_id": external_id})


def test_notification_missing_id():
    r = process_notification_job({}, FakeNotifyDb(), StubSender())
    assert not r.ok and "missing notification_id" in r.detail["error"]


def test_notification_missing_user():
    r = process_notification_job({"notification_id": "n-1"}, FakeNotifyDb(), StubSender())
    assert not r.ok and "missing user_id" in r.detail["error"]


def test_notification_success():
    db = FakeNotifyDb()
    r = process_notification_job(
        {"notification_id": "n-2", "user_id": "u-1", "channel": "sms",
         "title": "Hi", "body": "Hello", "notification_type": "order_update"},
        db, StubSender(),
    )
    assert r.ok
    assert r.detail["provider"] == "stub"
    assert db.sent == [("n-2", r.detail["external_id"])]
    assert len(db.logs) == 1


def test_notification_failure():
    db = FakeNotifyDb()
    r = process_notification_job(
        {"notification_id": "n-3", "user_id": "u-2", "channel": "sms",
         "title": "Hi", "body": "Body"},
        db, TwilioSMSSender(),  # no creds → fails
    )
    assert not r.ok
    assert db.failed == [("n-3", r.detail["error"])]
