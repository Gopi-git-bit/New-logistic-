BEGIN;

DROP POLICY IF EXISTS location_participant_access ON zippy.trip_location_history;
DROP TRIGGER IF EXISTS exception_status_history_append_only ON zippy.exception_status_history;
DROP TRIGGER IF EXISTS admin_actions_append_only ON zippy.admin_account_actions;
DROP TRIGGER IF EXISTS operational_events_append_only ON zippy.operational_events;
DROP TRIGGER IF EXISTS audit_events_append_only ON zippy.audit_events;
DROP TRIGGER IF EXISTS refund_executions_append_only ON zippy.refund_executions;
DROP TRIGGER IF EXISTS refund_decisions_append_only ON zippy.refund_decisions;
DROP TRIGGER IF EXISTS gateway_events_append_only ON zippy.gateway_events;
DROP TRIGGER IF EXISTS locations_append_only ON zippy.trip_location_history;
DROP TRIGGER IF EXISTS transitions_append_only ON zippy.order_state_transitions;
DROP TRIGGER IF EXISTS quotes_append_only ON zippy.quotes;
DROP TRIGGER IF EXISTS external_reference_identity_guard ON zippy.external_references;
DROP TRIGGER IF EXISTS refund_decision_self_approval_guard ON zippy.refund_decisions;
DROP TRIGGER IF EXISTS refund_execution_approval_guard ON zippy.refund_executions;
DROP TRIGGER IF EXISTS payment_projection_evidence_guard ON zippy.payment_projections;
DROP TRIGGER IF EXISTS location_authorization_guard ON zippy.trip_location_history;
DROP TRIGGER IF EXISTS milestone_sequence_guard ON zippy.trip_milestones;
DROP TRIGGER IF EXISTS transaction_participant_role_guard ON zippy.transaction_participants;
DROP TRIGGER IF EXISTS assignments_eligibility_guard ON zippy.trip_assignments;
DROP TRIGGER IF EXISTS accounts_status_guard ON zippy.accounts;
DROP TRIGGER IF EXISTS orders_status_guard ON zippy.orders;

DROP TABLE IF EXISTS zippy.operational_events;
DROP TABLE IF EXISTS zippy.order_state_transitions;
DROP TABLE IF EXISTS zippy.order_transition_rules;

DROP FUNCTION IF EXISTS zippy.fail_durable_task(uuid, uuid, text, text, timestamptz);
DROP FUNCTION IF EXISTS zippy.claim_durable_tasks(uuid, text, text, integer, integer);
DROP FUNCTION IF EXISTS zippy.protect_external_reference_identity();
DROP FUNCTION IF EXISTS zippy.validate_refund_decision();
DROP FUNCTION IF EXISTS zippy.validate_refund_execution();
DROP FUNCTION IF EXISTS zippy.validate_payment_projection();
DROP FUNCTION IF EXISTS zippy.validate_location_sample();
DROP FUNCTION IF EXISTS zippy.validate_milestone_sequence();
DROP FUNCTION IF EXISTS zippy.validate_transaction_participant();
DROP FUNCTION IF EXISTS zippy.validate_assignment();
DROP FUNCTION IF EXISTS zippy.set_account_status(uuid, uuid, uuid, zippy.account_status, text, text, uuid);
DROP FUNCTION IF EXISTS zippy.guard_account_status_update();
DROP FUNCTION IF EXISTS zippy.transition_order(uuid, uuid, zippy.order_status, zippy.order_status, uuid, text, text, text, uuid);
DROP FUNCTION IF EXISTS zippy.guard_order_status_update();
DROP FUNCTION IF EXISTS zippy.reject_mutation_of_history();

COMMIT;