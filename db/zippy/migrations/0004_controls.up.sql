BEGIN;

CREATE TABLE zippy.order_transition_rules (
    from_status zippy.order_status NOT NULL,
    to_status zippy.order_status NOT NULL,
    PRIMARY KEY (from_status, to_status),
    CHECK (from_status <> to_status)
);

INSERT INTO zippy.order_transition_rules (from_status, to_status) VALUES
    ('pending', 'quoted'),
    ('pending', 'cancelled'),
    ('quoted', 'confirmed'),
    ('quoted', 'cancelled'),
    ('confirmed', 'assigned'),
    ('confirmed', 'cancelled'),
    ('assigned', 'in_transit'),
    ('assigned', 'cancelled'),
    ('in_transit', 'delivered');

CREATE TABLE zippy.order_state_transitions (
    order_state_transition_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    platform_id uuid NOT NULL REFERENCES zippy.platforms(platform_id),
    order_id uuid NOT NULL,
    from_status zippy.order_status NOT NULL,
    to_status zippy.order_status NOT NULL,
    actor_account_id uuid NOT NULL,
    reason text NOT NULL,
    idempotency_key text NOT NULL,
    correlation_id uuid NOT NULL,
    occurred_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (platform_id, order_state_transition_id),
    UNIQUE (platform_id, order_id, idempotency_key),
    FOREIGN KEY (platform_id, order_id) REFERENCES zippy.orders(platform_id, order_id),
    FOREIGN KEY (platform_id, actor_account_id) REFERENCES zippy.accounts(platform_id, account_id),
    FOREIGN KEY (from_status, to_status) REFERENCES zippy.order_transition_rules(from_status, to_status)
);

CREATE TABLE zippy.operational_events (
    operational_event_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    platform_id uuid NOT NULL REFERENCES zippy.platforms(platform_id),
    aggregate_type text NOT NULL,
    aggregate_id uuid NOT NULL,
    aggregate_version integer NOT NULL CHECK (aggregate_version > 0),
    event_type text NOT NULL,
    event_data jsonb NOT NULL,
    actor_account_id uuid,
    correlation_id uuid NOT NULL,
    occurred_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (platform_id, operational_event_id),
    UNIQUE (platform_id, aggregate_type, aggregate_id, aggregate_version, event_type),
    FOREIGN KEY (platform_id, actor_account_id) REFERENCES zippy.accounts(platform_id, account_id),
    CHECK (jsonb_typeof(event_data) = 'object')
);

CREATE FUNCTION zippy.reject_mutation_of_history()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION '% is append-only', TG_TABLE_NAME USING ERRCODE = '55000';
END;
$$;

CREATE FUNCTION zippy.guard_order_status_update()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.status IS DISTINCT FROM OLD.status
       AND current_setting('zippy.transition_context', true) IS DISTINCT FROM 'allowed' THEN
        RAISE EXCEPTION 'orders.status must change through zippy.transition_order()' USING ERRCODE = '42501';
    END IF;
    RETURN NEW;
END;
$$;

CREATE FUNCTION zippy.transition_order(
    requested_platform_id uuid,
    requested_order_id uuid,
    expected_status zippy.order_status,
    requested_status zippy.order_status,
    requested_actor_account_id uuid,
    transition_reason text,
    request_idempotency_key text,
    requested_hash_sha256 text,
    request_correlation_id uuid
)
RETURNS zippy.order_status
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, zippy
SET row_security = on
AS $$
DECLARE
    current_status zippy.order_status;
    current_version integer;
    prior_hash text;
BEGIN
    IF nullif(current_setting('zippy.platform_id', true), '')::uuid IS DISTINCT FROM requested_platform_id
       OR nullif(current_setting('zippy.account_id', true), '')::uuid IS DISTINCT FROM requested_actor_account_id THEN
        RAISE EXCEPTION 'runtime platform/account context does not match transition actor' USING ERRCODE = '42501';
    END IF;
    IF NOT EXISTS (
        SELECT 1
          FROM zippy.accounts
         WHERE platform_id = requested_platform_id
           AND account_id = requested_actor_account_id
           AND status = 'active'
    ) THEN
        RAISE EXCEPTION 'blocked, suspended, pending, or unknown actor cannot transition orders' USING ERRCODE = '42501';
    END IF;

        SELECT record.request_hash_sha256 INTO prior_hash
            FROM zippy.idempotency_records record
         WHERE record.platform_id = requested_platform_id
             AND record.operation_scope = 'order_transition:' || requested_order_id::text
             AND record.idempotency_key = request_idempotency_key;

    IF prior_hash IS NOT NULL THEN
        IF prior_hash <> requested_hash_sha256 THEN
            RAISE EXCEPTION 'idempotency key reused with different request' USING ERRCODE = '23505';
        END IF;
        SELECT status INTO current_status
          FROM zippy.orders
         WHERE platform_id = requested_platform_id AND order_id = requested_order_id;
        RETURN current_status;
    END IF;

    SELECT status, version INTO current_status, current_version
      FROM zippy.orders
     WHERE platform_id = requested_platform_id AND order_id = requested_order_id
     FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'order not found' USING ERRCODE = 'P0002';
    END IF;
    IF current_status <> expected_status THEN
        RAISE EXCEPTION 'order status conflict: expected %, found %', expected_status, current_status USING ERRCODE = '40001';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM zippy.order_transition_rules
         WHERE from_status = current_status AND to_status = requested_status
    ) THEN
        RAISE EXCEPTION 'illegal order transition from % to %', current_status, requested_status USING ERRCODE = '23514';
    END IF;

    INSERT INTO zippy.idempotency_records (
        platform_id, operation_scope, idempotency_key, request_hash_sha256,
        status, correlation_id
    ) VALUES (
        requested_platform_id, 'order_transition:' || requested_order_id::text,
        request_idempotency_key, requested_hash_sha256, 'processing', request_correlation_id
    );

    PERFORM set_config('zippy.transition_context', 'allowed', true);
    UPDATE zippy.orders
       SET status = requested_status,
           version = version + 1,
           updated_at = clock_timestamp()
     WHERE platform_id = requested_platform_id AND order_id = requested_order_id;

    INSERT INTO zippy.order_state_transitions (
        platform_id, order_id, from_status, to_status, actor_account_id,
        reason, idempotency_key, correlation_id
    ) VALUES (
        requested_platform_id, requested_order_id, current_status, requested_status,
        requested_actor_account_id, transition_reason, request_idempotency_key, request_correlation_id
    );

    INSERT INTO zippy.operational_events (
        platform_id, aggregate_type, aggregate_id, aggregate_version,
        event_type, event_data, actor_account_id, correlation_id
    ) VALUES (
        requested_platform_id, 'order', requested_order_id, current_version + 1,
        'order.status_changed',
        jsonb_build_object('from', current_status, 'to', requested_status),
        requested_actor_account_id, request_correlation_id
    );

    INSERT INTO zippy.event_outbox (
        platform_id, aggregate_type, aggregate_id, aggregate_version, event_type,
        destination, payload, idempotency_key, correlation_id
    ) VALUES (
        requested_platform_id, 'order', requested_order_id, current_version + 1,
        'order.status_changed', 'internal',
        jsonb_build_object('order_id', requested_order_id, 'status', requested_status),
        request_idempotency_key, request_correlation_id
    );

    UPDATE zippy.idempotency_records
       SET status = 'succeeded', response_code = 200,
           response_reference = requested_order_id::text, completed_at = clock_timestamp()
     WHERE platform_id = requested_platform_id
       AND operation_scope = 'order_transition:' || requested_order_id::text
       AND idempotency_key = request_idempotency_key;

    RETURN requested_status;
END;
$$;

CREATE FUNCTION zippy.guard_account_status_update()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.status IS DISTINCT FROM OLD.status
       AND current_setting('zippy.account_control_context', true) IS DISTINCT FROM 'allowed' THEN
        RAISE EXCEPTION 'account status must change through zippy.set_account_status()' USING ERRCODE = '42501';
    END IF;
    RETURN NEW;
END;
$$;

CREATE FUNCTION zippy.set_account_status(
    requested_platform_id uuid,
    requested_affected_account_id uuid,
    requested_acting_admin_account_id uuid,
    requested_status zippy.account_status,
    requested_reason_code text,
    requested_reason_note text,
    request_correlation_id uuid
)
RETURNS zippy.account_status
LANGUAGE plpgsql
AS $$
DECLARE
    old_status zippy.account_status;
    action_kind zippy.admin_action_kind;
BEGIN
    IF requested_affected_account_id = requested_acting_admin_account_id THEN
        RAISE EXCEPTION 'admin cannot apply account control to self' USING ERRCODE = '23514';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM zippy.account_role_memberships
         WHERE platform_id = requested_platform_id
           AND account_id = requested_acting_admin_account_id
           AND role_code = 'admin'
           AND valid_from <= clock_timestamp()
           AND (valid_until IS NULL OR valid_until > clock_timestamp())
    ) THEN
        RAISE EXCEPTION 'acting account is not an active admin' USING ERRCODE = '42501';
    END IF;

    SELECT status INTO old_status
      FROM zippy.accounts
    WHERE platform_id = requested_platform_id AND account_id = requested_affected_account_id
     FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'account not found' USING ERRCODE = 'P0002';
    END IF;

    action_kind := CASE requested_status
        WHEN 'blocked' THEN 'block'::zippy.admin_action_kind
        WHEN 'suspended' THEN 'suspend'::zippy.admin_action_kind
        WHEN 'active' THEN 'unblock'::zippy.admin_action_kind
        ELSE NULL
    END;
    IF action_kind IS NULL OR old_status = requested_status THEN
        RAISE EXCEPTION 'unsupported account status transition' USING ERRCODE = '23514';
    END IF;

    PERFORM set_config('zippy.account_control_context', 'allowed', true);
    UPDATE zippy.accounts
       SET status = requested_status, updated_at = clock_timestamp()
    WHERE platform_id = requested_platform_id AND account_id = requested_affected_account_id;

    INSERT INTO zippy.admin_account_actions (
        platform_id, affected_account_id, acting_admin_account_id, action,
        previous_status, new_status, reason_code, reason_note, correlation_id
    ) VALUES (
        requested_platform_id, requested_affected_account_id, requested_acting_admin_account_id, action_kind,
        old_status, requested_status, requested_reason_code, requested_reason_note, request_correlation_id
    );

    IF requested_status IN ('blocked', 'suspended') AND EXISTS (
        SELECT 1
          FROM zippy.trip_assignments assignment
          JOIN zippy.trips trip
            ON trip.platform_id = assignment.platform_id AND trip.trip_id = assignment.trip_id
          JOIN zippy.driver_profiles driver
            ON driver.platform_id = assignment.platform_id AND driver.driver_profile_id = assignment.driver_profile_id
         WHERE assignment.platform_id = requested_platform_id
           AND driver.account_id = requested_affected_account_id
           AND assignment.released_at IS NULL
           AND trip.status IN ('assigned', 'active')
    ) THEN
        INSERT INTO zippy.operational_exceptions (
            platform_id, exception_code, severity, entity_type, entity_id,
            reason, correlation_id
        ) VALUES (
            requested_platform_id, 'ACCOUNT_BLOCKED_DURING_ACTIVE_TRIP', 'high',
            'account', requested_affected_account_id, requested_reason_code, request_correlation_id
        );
    END IF;

    RETURN requested_status;
END;
$$;

CREATE FUNCTION zippy.validate_assignment()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
                    FROM zippy.trips trip
                    JOIN zippy.dispatch_offers offer
                        ON offer.platform_id = trip.platform_id
                     AND offer.dispatch_offer_id = NEW.dispatch_offer_id
                     AND offer.order_id = trip.order_id
                     AND offer.status = 'accepted'
                     AND offer.vendor_profile_id = NEW.vendor_profile_id
                     AND offer.vehicle_id = NEW.vehicle_id
                     AND offer.driver_profile_id = NEW.driver_profile_id
                    JOIN zippy.transaction_participants participant
                        ON participant.platform_id = trip.platform_id
                     AND participant.order_id = trip.order_id
                     AND participant.participant_role = 'vendor'
                     AND participant.vendor_profile_id = NEW.vendor_profile_id
                    JOIN zippy.vehicles vehicle
                        ON vehicle.platform_id = trip.platform_id
                     AND vehicle.vehicle_id = NEW.vehicle_id
          JOIN zippy.vendor_profiles vendor
            ON vendor.platform_id = vehicle.platform_id AND vendor.vendor_profile_id = vehicle.vendor_profile_id
          JOIN zippy.driver_profiles driver
            ON driver.platform_id = vehicle.platform_id
           AND driver.driver_profile_id = NEW.driver_profile_id
                    JOIN zippy.accounts driver_account
                        ON driver_account.platform_id = driver.platform_id
                     AND driver_account.account_id = driver.account_id
                     AND driver_account.status = 'active'
          JOIN zippy.driver_associations association
            ON association.platform_id = driver.platform_id
           AND association.driver_profile_id = driver.driver_profile_id
           AND association.vendor_profile_id = vendor.vendor_profile_id
                 WHERE trip.platform_id = NEW.platform_id
                     AND trip.trip_id = NEW.trip_id
           AND vehicle.vendor_profile_id = NEW.vendor_profile_id
           AND vehicle.status = 'approved'
           AND vendor.eligibility_status = 'approved'
           AND driver.eligibility_status = 'approved'
                     AND (
                             (vendor.account_id IS NOT NULL AND EXISTS (
                                     SELECT 1
                                         FROM zippy.accounts vendor_account
                                        WHERE vendor_account.platform_id = vendor.platform_id
                                            AND vendor_account.account_id = vendor.account_id
                                            AND vendor_account.status = 'active'
                             ))
                             OR
                             (vendor.legal_entity_id IS NOT NULL AND EXISTS (
                                     SELECT 1
                                         FROM zippy.company_memberships membership
                                         JOIN zippy.accounts company_account
                                             ON company_account.platform_id = membership.platform_id
                                            AND company_account.account_id = membership.account_id
                                            AND company_account.status = 'active'
                                        WHERE membership.platform_id = vendor.platform_id
                                            AND membership.legal_entity_id = vendor.legal_entity_id
                                            AND membership.valid_from <= NEW.assigned_at
                                            AND (membership.valid_until IS NULL OR membership.valid_until > NEW.assigned_at)
                             ))
                     )
           AND association.valid_from <= NEW.assigned_at
           AND (association.valid_until IS NULL OR association.valid_until > NEW.assigned_at)
    ) THEN
        RAISE EXCEPTION 'assignment requires eligible vendor, vehicle, driver, and association' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$;

CREATE FUNCTION zippy.validate_transaction_participant()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.participant_role = 'customer' AND NOT EXISTS (
        SELECT 1
          FROM zippy.orders order_record
         WHERE order_record.platform_id = NEW.platform_id
           AND order_record.order_id = NEW.order_id
           AND order_record.booking_customer_profile_id = NEW.customer_profile_id
    ) THEN
        RAISE EXCEPTION 'customer participant must be the booking party' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$;

CREATE FUNCTION zippy.validate_milestone_sequence()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    expected_sequence integer;
BEGIN
    SELECT COALESCE(max(sequence_no), 0) + 1 INTO expected_sequence
      FROM zippy.trip_milestones
     WHERE platform_id = NEW.platform_id AND trip_id = NEW.trip_id;
    IF NEW.sequence_no <> expected_sequence THEN
        RAISE EXCEPTION 'milestone sequence must be %, received %', expected_sequence, NEW.sequence_no USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$;

CREATE FUNCTION zippy.validate_location_sample()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
          FROM zippy.trips trip
          JOIN zippy.trip_assignments assignment
            ON assignment.platform_id = trip.platform_id AND assignment.trip_id = trip.trip_id
          JOIN zippy.driver_profiles driver
            ON driver.platform_id = assignment.platform_id AND driver.driver_profile_id = assignment.driver_profile_id
         WHERE trip.platform_id = NEW.platform_id
           AND trip.trip_id = NEW.trip_id
           AND trip.status = 'active'
           AND assignment.vehicle_id = NEW.vehicle_id
           AND assignment.released_at IS NULL
           AND (driver.account_id = NEW.actor_account_id OR assignment.assigned_by_account_id = NEW.actor_account_id)
    ) THEN
        RAISE EXCEPTION 'location sample requires an active authorized trip assignment' USING ERRCODE = '42501';
    END IF;
    RETURN NEW;
END;
$$;

CREATE FUNCTION zippy.validate_payment_projection()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.operational_status = 'evidence_verified' AND NOT EXISTS (
        SELECT 1
          FROM zippy.gateway_events gateway_event
          JOIN zippy.webhook_receipts receipt
            ON receipt.platform_id = gateway_event.platform_id
           AND receipt.webhook_receipt_id = gateway_event.webhook_receipt_id
         WHERE gateway_event.platform_id = NEW.platform_id
           AND gateway_event.gateway_event_id = NEW.gateway_event_id
           AND gateway_event.order_id = NEW.order_id
           AND gateway_event.amount = NEW.amount
           AND gateway_event.currency_code = NEW.currency_code
           AND receipt.signature_verified
    ) THEN
        RAISE EXCEPTION 'verified payment projection requires matching signed gateway evidence' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$;

CREATE FUNCTION zippy.validate_refund_execution()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
          FROM zippy.refund_requests request
          JOIN zippy.refund_decisions decision
            ON decision.platform_id = request.platform_id
           AND decision.refund_request_id = request.refund_request_id
         WHERE request.platform_id = NEW.platform_id
           AND request.refund_request_id = NEW.refund_request_id
           AND decision.refund_decision_id = NEW.refund_decision_id
           AND decision.decision = 'approved'
           AND decision.approver_account_id <> request.requester_account_id
           AND request.amount = NEW.amount
           AND request.currency_code = NEW.currency_code
           AND request.target_reference = NEW.target_reference
    ) THEN
        RAISE EXCEPTION 'refund execution requires separate manual approval and exact request binding' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$;

CREATE FUNCTION zippy.validate_refund_decision()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF EXISTS (
        SELECT 1
          FROM zippy.refund_requests request
         WHERE request.platform_id = NEW.platform_id
           AND request.refund_request_id = NEW.refund_request_id
           AND request.requester_account_id = NEW.approver_account_id
    ) THEN
        RAISE EXCEPTION 'refund requester cannot approve own request' USING ERRCODE = '23514';
    END IF;
        IF NOT EXISTS (
                SELECT 1
                    FROM zippy.accounts account_record
                    JOIN zippy.account_role_memberships membership
                        ON membership.platform_id = account_record.platform_id
                     AND membership.account_id = account_record.account_id
                 WHERE account_record.platform_id = NEW.platform_id
                     AND account_record.account_id = NEW.approver_account_id
                     AND account_record.status = 'active'
                     AND membership.role_code = 'admin'
                     AND membership.valid_from <= clock_timestamp()
                     AND (membership.valid_until IS NULL OR membership.valid_until > clock_timestamp())
        ) THEN
                RAISE EXCEPTION 'refund decision requires an active authorized admin' USING ERRCODE = '42501';
        END IF;
    RETURN NEW;
END;
$$;

CREATE FUNCTION zippy.protect_external_reference_identity()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF ROW(
        NEW.platform_id, NEW.local_entity_type, NEW.local_entity_id,
        NEW.external_system, NEW.external_model, NEW.external_id
    ) IS DISTINCT FROM ROW(
        OLD.platform_id, OLD.local_entity_type, OLD.local_entity_id,
        OLD.external_system, OLD.external_model, OLD.external_id
    ) THEN
        RAISE EXCEPTION 'external reference identity is immutable' USING ERRCODE = '55000';
    END IF;
    RETURN NEW;
END;
$$;

CREATE FUNCTION zippy.claim_durable_tasks(
    requested_platform_id uuid,
    requested_task_type text,
    requested_lease_owner text,
    requested_lease_seconds integer,
    requested_limit integer
)
RETURNS SETOF zippy.durable_tasks
LANGUAGE sql
AS $$
    WITH candidates AS (
        SELECT durable_task_id
          FROM zippy.durable_tasks
         WHERE platform_id = requested_platform_id
           AND task_type = requested_task_type
           AND (
               (
                   status IN ('pending', 'failed')
                   AND next_attempt_at <= clock_timestamp()
                   AND (lease_expires_at IS NULL OR lease_expires_at <= clock_timestamp())
               ) OR (
                   status = 'processing'
                   AND lease_expires_at <= clock_timestamp()
               )
           )
         ORDER BY next_attempt_at, created_at
         FOR UPDATE SKIP LOCKED
         LIMIT requested_limit
    )
    UPDATE zippy.durable_tasks task
       SET status = 'processing',
           lease_owner = requested_lease_owner,
           lease_expires_at = clock_timestamp() + make_interval(secs => requested_lease_seconds),
           updated_at = clock_timestamp()
      FROM candidates
     WHERE task.platform_id = requested_platform_id
       AND task.durable_task_id = candidates.durable_task_id
    RETURNING task.*;
$$;

CREATE FUNCTION zippy.fail_durable_task(
    requested_platform_id uuid,
    requested_task_id uuid,
    requested_lease_owner text,
    failure_reason text,
    retry_at timestamptz
)
RETURNS zippy.processing_status
LANGUAGE plpgsql
AS $$
DECLARE
    updated_task zippy.durable_tasks%ROWTYPE;
BEGIN
    UPDATE zippy.durable_tasks
       SET attempt_count = attempt_count + 1,
           status = CASE WHEN attempt_count + 1 >= max_attempts THEN 'dead_lettered'::zippy.processing_status ELSE 'failed'::zippy.processing_status END,
           next_attempt_at = retry_at,
           lease_owner = NULL,
           lease_expires_at = NULL,
           updated_at = clock_timestamp()
     WHERE platform_id = requested_platform_id
       AND durable_task_id = requested_task_id
       AND status = 'processing'
       AND lease_owner = requested_lease_owner
    RETURNING * INTO updated_task;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'task lease not owned by caller' USING ERRCODE = '42501';
    END IF;

    IF updated_task.status = 'dead_lettered' THEN
        INSERT INTO zippy.dead_letter_records (
            platform_id, source_kind, source_id, terminal_reason,
            attempt_count, payload_reference, correlation_id
        ) VALUES (
            updated_task.platform_id, 'task', updated_task.durable_task_id,
            failure_reason, updated_task.attempt_count, updated_task.payload_reference,
            updated_task.correlation_id
        );
    END IF;

    RETURN updated_task.status;
END;
$$;

CREATE TRIGGER orders_status_guard
BEFORE UPDATE OF status ON zippy.orders
FOR EACH ROW EXECUTE FUNCTION zippy.guard_order_status_update();

CREATE TRIGGER accounts_status_guard
BEFORE UPDATE OF status ON zippy.accounts
FOR EACH ROW EXECUTE FUNCTION zippy.guard_account_status_update();

CREATE TRIGGER assignments_eligibility_guard
BEFORE INSERT ON zippy.trip_assignments
FOR EACH ROW EXECUTE FUNCTION zippy.validate_assignment();

CREATE TRIGGER transaction_participant_role_guard
BEFORE INSERT OR UPDATE ON zippy.transaction_participants
FOR EACH ROW EXECUTE FUNCTION zippy.validate_transaction_participant();

CREATE TRIGGER milestone_sequence_guard
BEFORE INSERT ON zippy.trip_milestones
FOR EACH ROW EXECUTE FUNCTION zippy.validate_milestone_sequence();

CREATE TRIGGER location_authorization_guard
BEFORE INSERT ON zippy.trip_location_history
FOR EACH ROW EXECUTE FUNCTION zippy.validate_location_sample();

CREATE TRIGGER payment_projection_evidence_guard
BEFORE INSERT OR UPDATE ON zippy.payment_projections
FOR EACH ROW EXECUTE FUNCTION zippy.validate_payment_projection();

CREATE TRIGGER refund_execution_approval_guard
BEFORE INSERT OR UPDATE ON zippy.refund_executions
FOR EACH ROW EXECUTE FUNCTION zippy.validate_refund_execution();

CREATE TRIGGER refund_decision_self_approval_guard
BEFORE INSERT OR UPDATE ON zippy.refund_decisions
FOR EACH ROW EXECUTE FUNCTION zippy.validate_refund_decision();

CREATE TRIGGER external_reference_identity_guard
BEFORE UPDATE ON zippy.external_references
FOR EACH ROW EXECUTE FUNCTION zippy.protect_external_reference_identity();

CREATE TRIGGER quotes_append_only
BEFORE UPDATE OR DELETE ON zippy.quotes
FOR EACH ROW EXECUTE FUNCTION zippy.reject_mutation_of_history();
CREATE TRIGGER transitions_append_only
BEFORE UPDATE OR DELETE ON zippy.order_state_transitions
FOR EACH ROW EXECUTE FUNCTION zippy.reject_mutation_of_history();
CREATE TRIGGER locations_append_only
BEFORE UPDATE OR DELETE ON zippy.trip_location_history
FOR EACH ROW EXECUTE FUNCTION zippy.reject_mutation_of_history();
CREATE TRIGGER gateway_events_append_only
BEFORE UPDATE OR DELETE ON zippy.gateway_events
FOR EACH ROW EXECUTE FUNCTION zippy.reject_mutation_of_history();
CREATE TRIGGER refund_decisions_append_only
BEFORE UPDATE OR DELETE ON zippy.refund_decisions
FOR EACH ROW EXECUTE FUNCTION zippy.reject_mutation_of_history();
CREATE TRIGGER refund_executions_append_only
BEFORE UPDATE OR DELETE ON zippy.refund_executions
FOR EACH ROW EXECUTE FUNCTION zippy.reject_mutation_of_history();
CREATE TRIGGER audit_events_append_only
BEFORE UPDATE OR DELETE ON zippy.audit_events
FOR EACH ROW EXECUTE FUNCTION zippy.reject_mutation_of_history();
CREATE TRIGGER operational_events_append_only
BEFORE UPDATE OR DELETE ON zippy.operational_events
FOR EACH ROW EXECUTE FUNCTION zippy.reject_mutation_of_history();
CREATE TRIGGER admin_actions_append_only
BEFORE UPDATE OR DELETE ON zippy.admin_account_actions
FOR EACH ROW EXECUTE FUNCTION zippy.reject_mutation_of_history();
CREATE TRIGGER exception_status_history_append_only
BEFORE UPDATE OR DELETE ON zippy.exception_status_history
FOR EACH ROW EXECUTE FUNCTION zippy.reject_mutation_of_history();

DO $$
DECLARE
    table_name text;
BEGIN
    FOR table_name IN
        SELECT tablename
          FROM pg_tables
         WHERE schemaname = 'zippy'
           AND tablename NOT IN ('schema_migrations', 'roles', 'order_transition_rules')
    LOOP
        EXECUTE format('ALTER TABLE zippy.%I ENABLE ROW LEVEL SECURITY', table_name);
        EXECUTE format('ALTER TABLE zippy.%I FORCE ROW LEVEL SECURITY', table_name);
        EXECUTE format(
            'CREATE POLICY platform_isolation ON zippy.%I USING (platform_id = nullif(current_setting(''zippy.platform_id'', true), '''')::uuid) WITH CHECK (platform_id = nullif(current_setting(''zippy.platform_id'', true), '''')::uuid)',
            table_name
        );
    END LOOP;
END
$$;

CREATE POLICY location_participant_access ON zippy.trip_location_history
AS RESTRICTIVE
USING (
        nullif(current_setting('zippy.account_id', true), '') IS NOT NULL
        AND (
                actor_account_id = nullif(current_setting('zippy.account_id', true), '')::uuid
                OR EXISTS (
                        SELECT 1
                            FROM zippy.account_role_memberships membership
                         WHERE membership.platform_id = trip_location_history.platform_id
                             AND membership.account_id = nullif(current_setting('zippy.account_id', true), '')::uuid
                             AND membership.role_code = 'admin'
                             AND membership.valid_from <= clock_timestamp()
                             AND (membership.valid_until IS NULL OR membership.valid_until > clock_timestamp())
                )
                OR EXISTS (
                        SELECT 1
                            FROM zippy.trips trip
                            JOIN zippy.transaction_participants participant
                                ON participant.platform_id = trip.platform_id
                             AND participant.order_id = trip.order_id
                            LEFT JOIN zippy.customer_profiles customer
                                ON customer.platform_id = participant.platform_id
                             AND customer.customer_profile_id = participant.customer_profile_id
                            LEFT JOIN zippy.vendor_profiles vendor
                                ON vendor.platform_id = participant.platform_id
                             AND vendor.vendor_profile_id = participant.vendor_profile_id
                            LEFT JOIN zippy.company_memberships company_member
                                ON company_member.platform_id = vendor.platform_id
                             AND company_member.legal_entity_id = vendor.legal_entity_id
                             AND company_member.valid_from <= clock_timestamp()
                             AND (company_member.valid_until IS NULL OR company_member.valid_until > clock_timestamp())
                         WHERE trip.platform_id = trip_location_history.platform_id
                             AND trip.trip_id = trip_location_history.trip_id
                             AND (
                                     customer.account_id = nullif(current_setting('zippy.account_id', true), '')::uuid
                                     OR vendor.account_id = nullif(current_setting('zippy.account_id', true), '')::uuid
                                     OR company_member.account_id = nullif(current_setting('zippy.account_id', true), '')::uuid
                             )
                )
        )
)
WITH CHECK (
        actor_account_id = nullif(current_setting('zippy.account_id', true), '')::uuid
        OR EXISTS (
                SELECT 1
                    FROM zippy.account_role_memberships membership
                 WHERE membership.platform_id = trip_location_history.platform_id
                     AND membership.account_id = nullif(current_setting('zippy.account_id', true), '')::uuid
                     AND membership.role_code = 'admin'
                     AND membership.valid_from <= clock_timestamp()
                     AND (membership.valid_until IS NULL OR membership.valid_until > clock_timestamp())
        )
);

REVOKE ALL ON ALL TABLES IN SCHEMA zippy FROM PUBLIC, zippy_app, zippy_readonly;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA zippy FROM PUBLIC, zippy_app, zippy_readonly;
REVOKE EXECUTE ON ALL FUNCTIONS IN SCHEMA zippy FROM PUBLIC, zippy_app, zippy_readonly;

GRANT SELECT ON ALL TABLES IN SCHEMA zippy TO zippy_app;
GRANT INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA zippy TO zippy_app;
REVOKE INSERT, UPDATE, DELETE ON zippy.schema_migrations, zippy.roles, zippy.order_transition_rules, zippy.platforms FROM zippy_app;
REVOKE UPDATE ON zippy.accounts, zippy.orders FROM zippy_app;
GRANT UPDATE (external_subject, email_normalized, phone_e164, updated_at) ON zippy.accounts TO zippy_app;
GRANT UPDATE (cargo_description, cargo_weight_kg, special_handling_code, updated_at) ON zippy.orders TO zippy_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA zippy TO zippy_app;
GRANT SELECT ON ALL TABLES IN SCHEMA zippy TO zippy_readonly;
GRANT EXECUTE ON FUNCTION zippy.transition_order(uuid, uuid, zippy.order_status, zippy.order_status, uuid, text, text, text, uuid) TO zippy_app;
GRANT EXECUTE ON FUNCTION zippy.claim_durable_tasks(uuid, text, text, integer, integer) TO zippy_app;
GRANT EXECUTE ON FUNCTION zippy.fail_durable_task(uuid, uuid, text, text, timestamptz) TO zippy_app;

COMMIT;