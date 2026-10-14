BEGIN;

DROP TABLE IF EXISTS zippy.notification_attempts;
DROP TABLE IF EXISTS zippy.sla_evidence;
DROP TABLE IF EXISTS zippy.service_commitments;
DROP TABLE IF EXISTS zippy.exception_status_history;
DROP TABLE IF EXISTS zippy.operational_exceptions;
DROP TABLE IF EXISTS zippy.audit_events;
DROP TABLE IF EXISTS zippy.dead_letter_records;
DROP TABLE IF EXISTS zippy.event_inbox;
DROP TABLE IF EXISTS zippy.event_outbox;
DROP TABLE IF EXISTS zippy.durable_tasks;
DROP TABLE IF EXISTS zippy.idempotency_records;
DROP TABLE IF EXISTS zippy.refund_executions;
DROP TABLE IF EXISTS zippy.refund_decisions;
DROP TABLE IF EXISTS zippy.refund_requests;
DROP TABLE IF EXISTS zippy.settlement_projections;
DROP TABLE IF EXISTS zippy.external_references;
DROP TABLE IF EXISTS zippy.financial_requests;
DROP TABLE IF EXISTS zippy.payment_projections;
DROP TABLE IF EXISTS zippy.gateway_events;
DROP TABLE IF EXISTS zippy.webhook_receipts;

DROP TYPE IF EXISTS zippy.exception_status;
DROP TYPE IF EXISTS zippy.refund_status;
DROP TYPE IF EXISTS zippy.financial_request_status;
DROP TYPE IF EXISTS zippy.processing_status;

COMMIT;