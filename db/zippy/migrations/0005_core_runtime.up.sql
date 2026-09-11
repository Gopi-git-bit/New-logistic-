BEGIN;

ALTER TABLE zippy.idempotency_records
    ADD COLUMN expires_at timestamptz NOT NULL DEFAULT (clock_timestamp() + interval '24 hours');

ALTER TABLE zippy.event_outbox
    ADD COLUMN max_attempts integer NOT NULL DEFAULT 5 CHECK (max_attempts > 0),
    ADD COLUMN lease_owner text,
    ADD COLUMN lease_expires_at timestamptz,
    ADD COLUMN last_error text,
    ADD CONSTRAINT event_outbox_lease_pair_check
        CHECK ((lease_owner IS NULL) = (lease_expires_at IS NULL)),
    ADD CONSTRAINT event_outbox_attempt_limit_check
        CHECK (attempt_count <= max_attempts),
    ADD CONSTRAINT event_outbox_dead_letter_limit_check
        CHECK (status <> 'dead_lettered' OR attempt_count = max_attempts);

CREATE OR REPLACE FUNCTION zippy.claim_durable_tasks(
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
           AND attempt_count < max_attempts
           AND next_attempt_at <= clock_timestamp()
           AND (
               status IN ('pending', 'failed')
               OR (status = 'processing' AND lease_expires_at <= clock_timestamp())
           )
         ORDER BY next_attempt_at, created_at
         FOR UPDATE SKIP LOCKED
         LIMIT LEAST(GREATEST(requested_limit, 1), 100)
    )
    UPDATE zippy.durable_tasks task
       SET status = 'processing',
           attempt_count = task.attempt_count + 1,
           lease_owner = requested_lease_owner,
           lease_expires_at = clock_timestamp() + make_interval(secs => requested_lease_seconds),
           updated_at = clock_timestamp()
      FROM candidates
     WHERE task.platform_id = requested_platform_id
       AND task.durable_task_id = candidates.durable_task_id
    RETURNING task.*;
$$;

CREATE OR REPLACE FUNCTION zippy.fail_durable_task(
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
       SET status = CASE WHEN attempt_count >= max_attempts THEN 'dead_lettered'::zippy.processing_status ELSE 'failed'::zippy.processing_status END,
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
            left(failure_reason, 1000), updated_task.attempt_count, updated_task.payload_reference,
            updated_task.correlation_id
        ) ON CONFLICT (platform_id, source_kind, source_id) DO NOTHING;
    END IF;

    RETURN updated_task.status;
END;
$$;

CREATE FUNCTION zippy.claim_outbox_events(
    requested_platform_id uuid,
    requested_worker text,
    requested_limit integer,
    requested_lease_seconds integer
)
RETURNS SETOF zippy.event_outbox
LANGUAGE sql
AS $$
    UPDATE zippy.event_outbox event
       SET status = 'processing',
           attempt_count = event.attempt_count + 1,
           lease_owner = requested_worker,
           lease_expires_at = clock_timestamp() + make_interval(secs => requested_lease_seconds)
     WHERE event.outbox_event_id IN (
        SELECT candidate.outbox_event_id
          FROM zippy.event_outbox candidate
         WHERE candidate.platform_id = requested_platform_id
           AND candidate.attempt_count < candidate.max_attempts
           AND candidate.next_attempt_at <= clock_timestamp()
           AND (
                candidate.status IN ('pending', 'failed')
                OR (candidate.status = 'processing' AND candidate.lease_expires_at <= clock_timestamp())
           )
         ORDER BY candidate.next_attempt_at, candidate.created_at
         FOR UPDATE SKIP LOCKED
         LIMIT LEAST(GREATEST(requested_limit, 1), 100)
     )
     RETURNING event.*;
$$;

CREATE FUNCTION zippy.complete_outbox_event(
    requested_platform_id uuid,
    requested_event_id uuid,
    requested_worker text
)
RETURNS boolean
LANGUAGE plpgsql
AS $$
BEGIN
    UPDATE zippy.event_outbox
       SET status = 'succeeded',
           published_at = clock_timestamp(),
           lease_owner = NULL,
           lease_expires_at = NULL,
           last_error = NULL
     WHERE platform_id = requested_platform_id
       AND outbox_event_id = requested_event_id
       AND status = 'processing'
       AND lease_owner = requested_worker;
    RETURN FOUND;
END;
$$;

CREATE FUNCTION zippy.fail_outbox_event(
    requested_platform_id uuid,
    requested_event_id uuid,
    requested_worker text,
    requested_error text,
    requested_next_attempt_at timestamptz
)
RETURNS zippy.processing_status
LANGUAGE plpgsql
AS $$
DECLARE
    resulting_status zippy.processing_status;
    event_record zippy.event_outbox%ROWTYPE;
BEGIN
    SELECT * INTO event_record
      FROM zippy.event_outbox
     WHERE platform_id = requested_platform_id
       AND outbox_event_id = requested_event_id
       AND status = 'processing'
       AND lease_owner = requested_worker
     FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'outbox lease not owned by worker' USING ERRCODE = '40001';
    END IF;

    resulting_status := CASE
        WHEN event_record.attempt_count >= event_record.max_attempts THEN 'dead_lettered'
        ELSE 'failed'
    END;

    UPDATE zippy.event_outbox
       SET status = resulting_status,
           next_attempt_at = requested_next_attempt_at,
           lease_owner = NULL,
           lease_expires_at = NULL,
           last_error = left(requested_error, 1000)
     WHERE platform_id = requested_platform_id
       AND outbox_event_id = requested_event_id;

    IF resulting_status = 'dead_lettered' THEN
        INSERT INTO zippy.dead_letter_records (
            platform_id, source_kind, source_id, terminal_reason,
            attempt_count, payload_reference, correlation_id
        ) VALUES (
            requested_platform_id, 'outbox', requested_event_id, left(requested_error, 1000),
            event_record.attempt_count, requested_event_id::text, event_record.correlation_id
        ) ON CONFLICT (platform_id, source_kind, source_id) DO NOTHING;

        INSERT INTO zippy.operational_exceptions (
            platform_id, exception_code, severity, entity_type, entity_id,
            reason, correlation_id
        ) VALUES (
            requested_platform_id, 'OUTBOX_DELIVERY_TERMINAL', 'high', 'outbox', requested_event_id,
            left(requested_error, 1000), event_record.correlation_id
        );
    END IF;

    RETURN resulting_status;
END;
$$;

REVOKE EXECUTE ON FUNCTION zippy.claim_outbox_events(uuid, text, integer, integer) FROM PUBLIC, zippy_readonly;
REVOKE EXECUTE ON FUNCTION zippy.complete_outbox_event(uuid, uuid, text) FROM PUBLIC, zippy_readonly;
REVOKE EXECUTE ON FUNCTION zippy.fail_outbox_event(uuid, uuid, text, text, timestamptz) FROM PUBLIC, zippy_readonly;
GRANT EXECUTE ON FUNCTION zippy.claim_outbox_events(uuid, text, integer, integer) TO zippy_app;
GRANT EXECUTE ON FUNCTION zippy.complete_outbox_event(uuid, uuid, text) TO zippy_app;
GRANT EXECUTE ON FUNCTION zippy.fail_outbox_event(uuid, uuid, text, text, timestamptz) TO zippy_app;

COMMIT;