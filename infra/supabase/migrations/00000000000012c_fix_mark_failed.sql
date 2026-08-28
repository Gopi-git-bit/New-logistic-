CREATE OR REPLACE FUNCTION public.mark_notification_failed(
    p_notification_id UUID,
    p_reason          TEXT DEFAULT NULL
) RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_row public.notification_queue%ROWTYPE;
BEGIN
    SELECT * INTO v_row
    FROM public.notification_queue
    WHERE notification_id = p_notification_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Notification % not found', p_notification_id;
    END IF;

    IF v_row.status != 'processing' THEN
        RAISE EXCEPTION 'Invalid notification transition to failed from %', v_row.status;
    END IF;

    IF v_row.attempts >= v_row.max_attempts THEN
        UPDATE public.notification_queue
           SET status = 'failed'
         WHERE notification_id = p_notification_id;
    ELSE
        UPDATE public.notification_queue
           SET status        = 'queued',
               next_retry_at = now() + (INTERVAL '1 minute' * POWER(5, v_row.attempts))
         WHERE notification_id = p_notification_id;
    END IF;
END;
$$;
