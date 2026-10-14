\set ON_ERROR_STOP on

\if :{?expected_session_user}
\else
  \echo 'expected_session_user is required'
  \quit 1
\endif

SELECT set_config('zippy.platform_id', '10000000-0000-0000-0000-000000000001', false);
SELECT set_config('zippy.account_id', 'a0000000-0000-0000-0000-000000000001', false);
SELECT set_config('zippy.expected_session_user', :'expected_session_user', false);

DO $$
BEGIN
  IF session_user <> current_setting('zippy.expected_session_user')
     OR current_user <> current_setting('zippy.expected_session_user') THEN
    RAISE EXCEPTION 'concurrency verification is not using the expected restricted LOGIN';
  END IF;
    IF (
        SELECT count(*)
          FROM zippy.durable_tasks
         WHERE task_type = 'synthetic_concurrent'
           AND status = 'processing'
    ) <> 2 THEN
        RAISE EXCEPTION 'concurrent claim did not claim exactly two tasks';
    END IF;

    IF (
        SELECT count(DISTINCT lease_owner)
          FROM zippy.durable_tasks
         WHERE task_type = 'synthetic_concurrent'
           AND status = 'processing'
    ) <> 2 THEN
        RAISE EXCEPTION 'concurrent claim reused a lease owner or double-claimed';
    END IF;
END;
$$;

SELECT 'Concurrent task claim passed' AS result;