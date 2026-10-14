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

CREATE TEMP TABLE expected_table_security (
    table_name text PRIMARY KEY,
    classification text NOT NULL
);

INSERT INTO expected_table_security (table_name, classification) VALUES
    ('schema_migrations', 'MIGRATION METADATA'),
    ('platforms', 'RLS REQUIRED'),
    ('accounts', 'RLS REQUIRED'),
    ('roles', 'JUSTIFIED EXEMPT'),
    ('account_role_memberships', 'RLS REQUIRED'),
    ('legal_entities', 'RLS REQUIRED'),
    ('customer_profiles', 'RLS REQUIRED'),
    ('vendor_profiles', 'RLS REQUIRED'),
    ('company_memberships', 'RLS REQUIRED'),
    ('driver_profiles', 'RLS REQUIRED'),
    ('driver_associations', 'RLS REQUIRED'),
    ('admin_account_actions', 'IMMUTABLE AUDIT'),
    ('vehicle_models', 'RLS REQUIRED'),
    ('vehicles', 'RLS REQUIRED'),
    ('vehicle_documents', 'RLS REQUIRED'),
    ('quotes', 'IMMUTABLE AUDIT'),
    ('orders', 'RLS REQUIRED'),
    ('order_stops', 'RLS REQUIRED'),
    ('transaction_participants', 'RLS REQUIRED'),
    ('dispatch_offers', 'RLS REQUIRED'),
    ('trips', 'RLS REQUIRED'),
    ('trip_assignments', 'RLS REQUIRED'),
    ('trip_milestones', 'RLS REQUIRED'),
    ('trip_location_history', 'IMMUTABLE AUDIT'),
    ('pod_documents', 'RLS REQUIRED'),
    ('webhook_receipts', 'INTERNAL WORKER'),
    ('gateway_events', 'IMMUTABLE AUDIT'),
    ('payment_projections', 'RLS REQUIRED'),
    ('financial_requests', 'RLS REQUIRED'),
    ('external_references', 'RLS REQUIRED'),
    ('settlement_projections', 'RLS REQUIRED'),
    ('refund_requests', 'RLS REQUIRED'),
    ('refund_decisions', 'IMMUTABLE AUDIT'),
    ('refund_executions', 'IMMUTABLE AUDIT'),
    ('idempotency_records', 'INTERNAL WORKER'),
    ('durable_tasks', 'INTERNAL WORKER'),
    ('event_outbox', 'INTERNAL WORKER'),
    ('event_inbox', 'INTERNAL WORKER'),
    ('dead_letter_records', 'INTERNAL WORKER'),
    ('audit_events', 'IMMUTABLE AUDIT'),
    ('operational_exceptions', 'RLS REQUIRED'),
    ('exception_status_history', 'IMMUTABLE AUDIT'),
    ('service_commitments', 'RLS REQUIRED'),
    ('sla_evidence', 'RLS REQUIRED'),
    ('notification_attempts', 'INTERNAL WORKER'),
    ('order_transition_rules', 'JUSTIFIED EXEMPT'),
    ('order_state_transitions', 'IMMUTABLE AUDIT'),
    ('operational_events', 'IMMUTABLE AUDIT'),
    ('payment_intents', 'RLS REQUIRED'),
    ('dispatch_requirements', 'RLS REQUIRED');

SELECT pg_temp.assert_true(session_user = :'expected_session_user', 'security suite uses the restricted application LOGIN');
SELECT pg_temp.assert_true(current_user = :'expected_session_user', 'security suite does not impersonate the object owner');
SELECT pg_temp.assert_true(pg_has_role(current_user, 'zippy_app', 'member'), 'application LOGIN has only intended group membership');
SELECT pg_temp.assert_true(
    (SELECT array_agg(parent.rolname ORDER BY parent.rolname)
       FROM pg_auth_members membership
       JOIN pg_roles parent ON parent.oid = membership.roleid
       JOIN pg_roles member ON member.oid = membership.member
      WHERE member.rolname = current_user) = ARRAY['zippy_app']::name[],
    'application LOGIN has exactly one group membership'
);
SELECT pg_temp.assert_true(
    NOT pg_has_role(current_user, 'zippy_migrator', 'member'),
    'application runtime is not a migration-role member'
);
SELECT pg_temp.assert_true(
    NOT (SELECT rolsuper OR rolcreaterole OR rolcreatedb OR rolbypassrls FROM pg_roles WHERE rolname = current_user),
    'application LOGIN has no elevated role attributes'
);
SELECT pg_temp.assert_true(
    (SELECT count(*)
       FROM pg_roles
      WHERE rolname IN ('zippy_migrator', 'zippy_app', 'zippy_readonly')
        AND NOT rolcanlogin
        AND NOT rolsuper
        AND NOT rolcreatedb
        AND NOT rolcreaterole
        AND NOT rolbypassrls) = 3,
    'all group roles are NOLOGIN and non-privileged'
);
SELECT pg_temp.assert_true(
    (SELECT count(*)
       FROM pg_roles
      WHERE rolname IN ('zippy_m2_migration_login', 'zippy_m2_app_login', 'zippy_m2_readonly_login')
        AND rolcanlogin
        AND NOT rolsuper
        AND NOT rolcreatedb
        AND NOT rolcreaterole
        AND NOT rolbypassrls) = 3,
    'all disposable LOGIN roles are non-privileged'
);
SELECT pg_temp.assert_true((SELECT count(*) FROM expected_table_security) = 50, 'all 50 tables are classified exactly once');
SELECT pg_temp.assert_true(
    NOT EXISTS (
        SELECT table_name FROM expected_table_security
        EXCEPT
        SELECT tablename FROM pg_tables WHERE schemaname = 'zippy'
    )
    AND NOT EXISTS (
        SELECT tablename FROM pg_tables WHERE schemaname = 'zippy'
        EXCEPT
        SELECT table_name FROM expected_table_security
    ),
    'classification and catalog table membership match exactly'
);
SELECT pg_temp.assert_true(
    (SELECT count(*) FROM expected_table_security WHERE classification = 'RLS REQUIRED') = 30
    AND (SELECT count(*) FROM expected_table_security WHERE classification = 'INTERNAL WORKER') = 7
    AND (SELECT count(*) FROM expected_table_security WHERE classification = 'IMMUTABLE AUDIT') = 10
    AND (SELECT count(*) FROM expected_table_security WHERE classification = 'MIGRATION METADATA') = 1
    AND (SELECT count(*) FROM expected_table_security WHERE classification = 'JUSTIFIED EXEMPT') = 2,
    'table classification totals are stable'
);
SELECT pg_temp.assert_true(
    NOT EXISTS (
        SELECT 1
          FROM expected_table_security expected
          JOIN pg_class relation ON relation.relname = expected.table_name
          JOIN pg_namespace namespace ON namespace.oid = relation.relnamespace AND namespace.nspname = 'zippy'
         WHERE expected.classification NOT IN ('MIGRATION METADATA', 'JUSTIFIED EXEMPT')
           AND (NOT relation.relrowsecurity OR NOT relation.relforcerowsecurity)
    ),
    'all 47 tenant-scoped internal, audit, and operational tables have enabled and forced RLS'
);
SELECT pg_temp.assert_true(
    (SELECT count(*) FROM pg_policies WHERE schemaname = 'zippy' AND policyname = 'platform_isolation') = 47,
    'all 47 tenant-scoped tables have a platform isolation policy'
);
SELECT pg_temp.assert_true(
    EXISTS (
        SELECT 1 FROM pg_policies
         WHERE schemaname = 'zippy'
           AND tablename = 'trip_location_history'
           AND policyname = 'location_participant_access'
           AND permissive = 'RESTRICTIVE'
    ),
    'location history has a restrictive participant policy'
);
SELECT pg_temp.assert_true(
    NOT EXISTS (
        SELECT 1 FROM pg_tables
         WHERE schemaname = 'zippy' AND tableowner <> 'zippy_migrator'
    ),
    'all Zippy tables are owned by the NOLOGIN migration role'
);
SELECT pg_temp.assert_true(
    NOT has_schema_privilege(current_user, 'zippy', 'CREATE')
    AND NOT has_database_privilege(current_user, current_database(), 'CREATE'),
    'application LOGIN cannot create schema objects'
);
SELECT pg_temp.assert_true(
        NOT EXISTS (
                SELECT 1
                    FROM pg_default_acl default_acl
                    CROSS JOIN LATERAL aclexplode(COALESCE(default_acl.defaclacl, acldefault(default_acl.defaclobjtype, default_acl.defaclrole))) privilege
                 WHERE default_acl.defaclnamespace = 'zippy'::regnamespace
                     AND privilege.grantee = 0
                     AND privilege.privilege_type IN ('INSERT', 'UPDATE', 'DELETE', 'TRUNCATE', 'REFERENCES', 'TRIGGER', 'EXECUTE', 'USAGE')
        ),
        'migrator default privileges do not grant PUBLIC mutation or execution'
);
SELECT pg_temp.assert_true(
        NOT EXISTS (
                SELECT 1
                    FROM pg_class sequence_record
                    JOIN pg_namespace namespace ON namespace.oid = sequence_record.relnamespace
                 WHERE namespace.nspname = 'zippy'
                     AND sequence_record.relkind = 'S'
                         AND has_sequence_privilege(
                                 'public',
                                 format('%I.%I', namespace.nspname, sequence_record.relname),
                                 'USAGE'
                         )
        ),
        'PUBLIC has no sequence usage'
);
SELECT pg_temp.assert_true(
    NOT has_table_privilege(current_user, 'zippy.schema_migrations', 'INSERT')
    AND NOT has_table_privilege(current_user, 'zippy.roles', 'UPDATE')
    AND NOT has_table_privilege(current_user, 'zippy.order_transition_rules', 'DELETE')
    AND NOT has_table_privilege(current_user, 'zippy.platforms', 'INSERT'),
    'application LOGIN cannot mutate migration or global control tables'
);
SELECT pg_temp.assert_true(
    NOT has_column_privilege(current_user, 'zippy.accounts', 'status', 'UPDATE')
    AND NOT has_column_privilege(current_user, 'zippy.orders', 'status', 'UPDATE'),
    'application LOGIN cannot update protected status columns directly'
);
SELECT pg_temp.assert_true(
    has_function_privilege(current_user, 'zippy.transition_order(uuid,uuid,zippy.order_status,zippy.order_status,uuid,text,text,text,uuid)', 'EXECUTE')
    AND has_function_privilege(current_user, 'zippy.claim_durable_tasks(uuid,text,text,integer,integer)', 'EXECUTE')
    AND has_function_privilege(current_user, 'zippy.fail_durable_task(uuid,uuid,text,text,timestamptz)', 'EXECUTE')
    AND has_function_privilege(current_user, 'zippy.claim_outbox_events(uuid,text,integer,integer)', 'EXECUTE')
    AND has_function_privilege(current_user, 'zippy.complete_outbox_event(uuid,uuid,text)', 'EXECUTE')
    AND has_function_privilege(current_user, 'zippy.fail_outbox_event(uuid,uuid,text,text,timestamptz)', 'EXECUTE')
    AND NOT has_function_privilege(current_user, 'zippy.set_account_status(uuid,uuid,uuid,zippy.account_status,text,text,uuid)', 'EXECUTE'),
    'application function execution is explicitly allowlisted'
);
SELECT pg_temp.assert_true(
    NOT has_schema_privilege('public', 'zippy', 'USAGE')
    AND NOT EXISTS (
        SELECT 1
          FROM information_schema.role_table_grants
         WHERE table_schema = 'zippy' AND grantee = 'PUBLIC'
    )
    AND NOT EXISTS (
        SELECT 1
          FROM information_schema.routine_privileges
         WHERE specific_schema = 'zippy' AND grantee = 'PUBLIC'
    ),
    'PUBLIC has no Zippy schema, table, or function privileges'
);

DO $$
BEGIN
    BEGIN
        EXECUTE 'CREATE TABLE zippy.application_forbidden_create(id integer)';
        RAISE EXCEPTION 'expected CREATE denial';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
    BEGIN
        EXECUTE 'ALTER TABLE zippy.orders ADD COLUMN application_forbidden_alter integer';
        RAISE EXCEPTION 'expected ALTER denial';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
    BEGIN
        EXECUTE 'DROP TABLE zippy.orders';
        RAISE EXCEPTION 'expected DROP denial';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
    BEGIN
        UPDATE zippy.orders SET status = 'cancelled';
        RAISE EXCEPTION 'expected direct order-status update denial';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
END;
$$;

SELECT 'Application role, ownership, privilege, and RLS catalog assertions passed' AS result;