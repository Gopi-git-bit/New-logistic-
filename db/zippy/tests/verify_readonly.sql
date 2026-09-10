\set ON_ERROR_STOP on

\if :{?expected_session_user}
\else
    \echo 'expected_session_user is required'
    \quit 1
\endif

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

SELECT set_config('zippy.platform_id', '10000000-0000-0000-0000-000000000001', false);
SELECT set_config('zippy.account_id', 'c0000000-0000-0000-0000-000000000001', false);
SELECT pg_temp.assert_true(session_user = :'expected_session_user', 'read-only suite uses the restricted read-only LOGIN');
SELECT pg_temp.assert_true(current_user = :'expected_session_user', 'read-only suite does not impersonate another role');
SELECT pg_temp.assert_true(pg_has_role(current_user, 'zippy_readonly', 'member'), 'read-only LOGIN has intended group membership');
SELECT pg_temp.assert_true(
        (SELECT array_agg(parent.rolname ORDER BY parent.rolname)
             FROM pg_auth_members membership
             JOIN pg_roles parent ON parent.oid = membership.roleid
             JOIN pg_roles member ON member.oid = membership.member
            WHERE member.rolname = current_user) = ARRAY['zippy_readonly']::name[],
        'read-only LOGIN has exactly one group membership'
);
SELECT pg_temp.assert_true(
    NOT (SELECT rolsuper OR rolcreaterole OR rolcreatedb OR rolbypassrls FROM pg_roles WHERE rolname = current_user),
    'read-only LOGIN has no elevated role attributes'
);
SELECT pg_temp.assert_true((SELECT count(*) FROM zippy.accounts) = 8, 'read-only role can read its selected platform');
SELECT pg_temp.assert_true(
    NOT EXISTS (SELECT 1 FROM zippy.accounts WHERE platform_id = '20000000-0000-0000-0000-000000000002'),
    'read-only RLS hides another platform'
);

DO $$
BEGIN
    BEGIN
        INSERT INTO zippy.audit_events (
            platform_id, actor_type, action, entity_type, entity_id, correlation_id
        ) VALUES (
            '10000000-0000-0000-0000-000000000001', 'service', 'forbidden', 'order',
            '30000000-0000-0000-0000-000000000001', '90000000-0000-0000-0000-000000000090'
        );
        RAISE EXCEPTION 'expected read-only insert denial';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
    BEGIN
        UPDATE zippy.orders SET cargo_description = 'forbidden';
        RAISE EXCEPTION 'expected read-only update denial';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
    BEGIN
        DELETE FROM zippy.audit_events;
        RAISE EXCEPTION 'expected read-only delete denial';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
    BEGIN
        PERFORM zippy.transition_order(
            '10000000-0000-0000-0000-000000000001', '30000000-0000-0000-0000-000000000001',
            'quoted', 'confirmed', 'c0000000-0000-0000-0000-000000000001', 'forbidden',
            'readonly-forbidden', repeat('f', 64), '90000000-0000-0000-0000-000000000091'
        );
        RAISE EXCEPTION 'expected read-only function denial';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
END;
$$;

SELECT 'Read-only role and RLS assertions passed' AS result;