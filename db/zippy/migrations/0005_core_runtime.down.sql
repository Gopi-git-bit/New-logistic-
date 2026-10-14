BEGIN;

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

DROP FUNCTION zippy.fail_outbox_event(uuid, uuid, text, text, timestamptz);
DROP FUNCTION zippy.complete_outbox_event(uuid, uuid, text);
DROP FUNCTION zippy.claim_outbox_events(uuid, text, integer, integer);

ALTER TABLE zippy.event_outbox
    DROP CONSTRAINT event_outbox_dead_letter_limit_check,
    DROP CONSTRAINT event_outbox_attempt_limit_check,
    DROP CONSTRAINT event_outbox_lease_pair_check,
    DROP COLUMN last_error,
    DROP COLUMN lease_expires_at,
    DROP COLUMN lease_owner,
    DROP COLUMN max_attempts;

ALTER TABLE zippy.idempotency_records
    DROP COLUMN expires_at;

COMMIT;