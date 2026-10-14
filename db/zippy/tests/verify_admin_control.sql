\set ON_ERROR_STOP on

CREATE OR REPLACE FUNCTION pg_temp.assert_true(condition boolean, message text)
RETURNS void
LANGUAGE plpgsql
AS $$
BEGIN
    IF condition IS DISTINCT FROM true THEN
        RAISE EXCEPTION 'assertion failed: %', message;
    END IF;
END;
$$;

SELECT pg_temp.assert_true(current_user = 'zippy_migrator', 'admin-control test runs as the migration owner');
SELECT set_config('zippy.platform_id', '10000000-0000-0000-0000-000000000001', false);
SELECT set_config('zippy.account_id', 'a0000000-0000-0000-0000-000000000001', false);
SELECT pg_temp.assert_true(
    (SELECT count(*) FROM zippy.accounts) = 8
    AND NOT EXISTS (SELECT 1 FROM zippy.accounts WHERE platform_id = '20000000-0000-0000-0000-000000000002'),
    'FORCE RLS applies to the table-owning migration role'
);

CREATE TEMP TABLE control_baseline AS
SELECT
    (SELECT count(*) FROM zippy.refund_executions) AS refund_count,
    (SELECT count(*) FROM zippy.settlement_projections) AS settlement_count,
    (SELECT status FROM zippy.trips WHERE trip_id = '40000000-0000-0000-0000-000000000001') AS trip_status;

SELECT pg_temp.assert_true(
    zippy.set_account_status(
        '10000000-0000-0000-0000-000000000001', 'd0000000-0000-0000-0000-000000000001',
        'a0000000-0000-0000-0000-000000000001', 'blocked', 'synthetic_safety',
        'synthetic block during active trip', '90000000-0000-0000-0000-000000000042'
    ) = 'blocked',
    'migration-owned control can block account with audit'
);
SELECT pg_temp.assert_true(
    (SELECT count(*) FROM zippy.operational_exceptions WHERE exception_code = 'ACCOUNT_BLOCKED_DURING_ACTIVE_TRIP') = 1,
    'blocking an active driver opens an exception'
);
SELECT pg_temp.assert_true(
    (SELECT status FROM zippy.trips WHERE trip_id = '40000000-0000-0000-0000-000000000001') = (SELECT trip_status FROM control_baseline),
    'blocking does not cancel or alter the active trip'
);
SELECT pg_temp.assert_true(
    (SELECT count(*) FROM zippy.refund_executions) = (SELECT refund_count FROM control_baseline),
    'blocking does not create a refund'
);
SELECT pg_temp.assert_true(
    (SELECT count(*) FROM zippy.settlement_projections) = (SELECT settlement_count FROM control_baseline),
    'blocking does not alter settlement evidence'
);
SELECT pg_temp.assert_true(
    zippy.set_account_status(
        '10000000-0000-0000-0000-000000000001', 'd0000000-0000-0000-0000-000000000001',
        'a0000000-0000-0000-0000-000000000001', 'active', 'synthetic_review_complete',
        'synthetic unblock', '90000000-0000-0000-0000-000000000043'
    ) = 'active',
    'migration-owned control can restore account after review'
);

SELECT 'Admin account-control assertions passed' AS result;