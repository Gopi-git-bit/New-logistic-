-- Prepares one approved grant as the restricted role and prints only its id; run_m5_proof.sh races two consumers against it.
\set ON_ERROR_STOP 1
\o /dev/null
SET ROLE paperclip_app;
SELECT set_config('paperclip.tenant_id', '11111111-1111-1111-1111-111111111111', false);
SELECT (paperclip.create_proposal('11111111-1111-1111-1111-111111111112', '11111111-1111-1111-1111-111111111113', 'REFUND', 'ZIPPY', 'order', 'concurrency', '{"ref":"conc"}'::jsonb, 'conc-1', now() + interval '10 minutes')).governance_id AS p_conc \gset
SELECT paperclip.record_invariant(:'p_conc', 'INV-1', true);
SELECT paperclip.decide(:'p_conc', 'Gopinathan', true, now() + interval '5 minutes');
\o
SELECT (paperclip.issue_grant(:'p_conc')).governance_id;