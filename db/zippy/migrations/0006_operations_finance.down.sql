BEGIN;

DROP TABLE IF EXISTS zippy.dispatch_requirements;
DROP TABLE IF EXISTS zippy.payment_intents;
DROP TRIGGER IF EXISTS settlement_projection_pod_gate ON zippy.settlement_projections;
DROP FUNCTION IF EXISTS zippy.validate_settlement_projection();
DROP INDEX IF EXISTS zippy.webhook_receipts_processing_idx;

-- Disposable-only rollback: clear projection rows so the NOT NULL constraint can
-- be restored. TRUNCATE is unaffected by forced RLS; down migrations are
-- destructive and disposable-only by design. Production recovery is forward-fix.
TRUNCATE zippy.settlement_projections;

ALTER TABLE zippy.settlement_projections
    ALTER COLUMN financial_request_id SET NOT NULL;

COMMIT;
