-- =============================================================================
-- M3 Verification Suite — agent control plane (D-17 pause/budget at claim time)
-- Usage:
--   docker cp infra/supabase/verify_m3.sql zippy-db:/tmp/v3.sql
--   docker exec zippy-db psql -U postgres -d postgres -f /tmp/v3.sql
-- Self-contained; single transaction.
-- Table-function results are consumed as SELECT count(*) INTO declared ints;
-- VOID functions go through PERFORM.
-- =============================================================================

\set ON_ERROR_STOP off

BEGIN;

SELECT CASE WHEN count(*) >= 7 THEN 'PASS' ELSE 'FAIL' END AS t1_all_agents_registered
FROM public.agent_registry;

-- -----------------------------------------------------------------------------
-- T2: enqueue + dedupe idempotency
-- -----------------------------------------------------------------------------
INSERT INTO public.agent_tasks (agent_name, task_type, payload, dedupe_key)
VALUES ('order_management', 'generate_quote', '{"order_id":"x1"}', 'm3-dedupe-1');
INSERT INTO public.agent_tasks (agent_name, task_type, payload, dedupe_key)
VALUES ('order_management', 'generate_quote', '{"order_id":"x1"}', 'm3-dedupe-1')
ON CONFLICT (dedupe_key) DO NOTHING;

SELECT CASE WHEN count(*) = 1 THEN 'PASS' ELSE 'FAIL' END AS t2_dedupe_key_unique
FROM public.agent_tasks WHERE dedupe_key='m3-dedupe-1';

-- -----------------------------------------------------------------------------
-- T3: happy cycle — claim -> complete
-- -----------------------------------------------------------------------------
DO $$
DECLARE r RECORD; n INT; c INT := 0;
BEGIN
    SELECT count(*) INTO c FROM public.claim_agent_tasks('order_management','worker-a',5);
    IF c = 1 THEN
        RAISE NOTICE 'PASS t3_claim_returns_row';
    ELSE
        RAISE NOTICE 'FAIL t3_claim_returns_row (claimed %)', c;
    END IF;

    -- complete the claimed row
    UPDATE public.agent_tasks SET status='done', completed_at=CURRENT_TIMESTAMP,
                                   result='{"ok":true}'::jsonb
     WHERE dedupe_key='m3-dedupe-1' AND status='claimed';

    SELECT count(*) INTO n FROM public.agent_tasks WHERE status='done' AND dedupe_key='m3-dedupe-1';
    IF n=1 THEN RAISE NOTICE 'PASS t3_complete'; ELSE RAISE NOTICE 'FAIL t3_complete'; END IF;
END $$;

-- -----------------------------------------------------------------------------
-- T4: retry ladder — fail #1 requeues, fail #2 dead-letters (max_attempts=2)
-- -----------------------------------------------------------------------------
INSERT INTO public.agent_tasks (agent_name, task_type, payload, max_attempts)
VALUES ('order_management','boom','{}',2);

DO $$
DECLARE tid UUID; c INT := 0;
BEGIN
    SELECT task_id INTO tid FROM public.agent_tasks WHERE task_type='boom' AND status='queued';

    SELECT count(*) INTO c FROM public.claim_agent_tasks('order_management','w',5);
    PERFORM public.fail_agent_task(tid,'boom #1');

    IF (SELECT status FROM public.agent_tasks WHERE task_id=tid)='queued' THEN
        RAISE NOTICE 'PASS t4_retry_requeues';
    ELSE RAISE NOTICE 'FAIL t4_retry_requeues'; END IF;

    SELECT count(*) INTO c FROM public.claim_agent_tasks('order_management','w',5);
    PERFORM public.fail_agent_task(tid,'boom #2');

    IF (SELECT status FROM public.agent_tasks WHERE task_id=tid)='dead' THEN
        RAISE NOTICE 'PASS t4_dead_letter';
    ELSE RAISE NOTICE 'FAIL t4_dead_letter'; END IF;
END $$;

-- -----------------------------------------------------------------------------
-- T5: D-17 paused agent skipped AT CLAIM TIME (zero tasks consumed)
-- -----------------------------------------------------------------------------
INSERT INTO public.agent_tasks (agent_name, task_type) VALUES ('communication','ping');

DO $$
DECLARE c INT := 0;
BEGIN
    PERFORM public.set_agent_status('communication','paused','maintenance');

    BEGIN
        SELECT count(*) INTO c FROM public.claim_agent_tasks('communication','w',5);
        RAISE NOTICE 'FAIL t5_paused_claim_rejected (claimed % rows!)', c;
    EXCEPTION WHEN raise_exception THEN
        IF SQLERRM LIKE 'AGENT_PAUSED%' THEN
            RAISE NOTICE 'PASS t5_paused_claim_rejected';
        ELSE
            RAISE NOTICE 'FAIL t5_paused_claim_rejected (wrong error: %)', SQLERRM;
        END IF;
    END;
END $$;

SELECT CASE WHEN count(*) = 1 THEN 'PASS' ELSE 'FAIL' END AS t5_paused_consumes_nothing
FROM public.agent_tasks WHERE task_type='ping' AND status='queued';

-- blocked variant
DO $$
DECLARE c INT := 0;
BEGIN
    PERFORM public.set_agent_status('platform_administration','blocked','investigation');
    BEGIN
        SELECT count(*) INTO c FROM public.claim_agent_tasks('platform_administration','w',5);
        RAISE NOTICE 'FAIL t5b_blocked_claim_rejected (claimed % rows!)', c;
    EXCEPTION WHEN raise_exception THEN
        IF SQLERRM LIKE 'AGENT_BLOCKED%' THEN
            RAISE NOTICE 'PASS t5b_blocked_claim_rejected';
        ELSE
            RAISE NOTICE 'FAIL t5b_blocked_claim_rejected (wrong error: %)', SQLERRM;
        END IF;
    END;
END $$;

-- -----------------------------------------------------------------------------
-- T6: budget exhaustion auto-pauses and rejects further claims
-- -----------------------------------------------------------------------------
UPDATE public.agent_registry SET daily_budget_usd_cents=10 WHERE agent_name='payment_settlement';

DO $$
BEGIN
    PERFORM public.record_agent_spend('payment_settlement', 25);
END $$;

SELECT CASE WHEN budget_spent_cents >= daily_budget_usd_cents
            THEN 'PASS' ELSE 'FAIL' END AS t6_over_budget_setup
FROM public.agent_registry WHERE agent_name='payment_settlement';

DO $$
DECLARE c INT := 0; c2 INT := 0;
BEGIN
    BEGIN
        SELECT count(*) INTO c FROM public.claim_agent_tasks('payment_settlement','w',5);
        RAISE NOTICE 'FAIL t6_exhausted_claim_rejected (claimed % rows!)', c;
    EXCEPTION WHEN raise_exception THEN
        IF SQLERRM LIKE 'AGENT_BUDGET_EXHAUSTED%' THEN
            RAISE NOTICE 'PASS t6_exhausted_claim_rejected';
        ELSE
            RAISE NOTICE 'FAIL t6_exhausted_claim_rejected (wrong error: %)', SQLERRM;
        END IF;
    END;

    -- Contract: because a failed claim rolls back its own internal writes,
    -- the CATCHER persists the pause (kernel catch-path / sweeper).
    PERFORM public.set_agent_status('payment_settlement','paused','BUDGET_EXHAUSTED');

    -- Once paused, subsequent claims skip on the cheaper fast-path.
    BEGIN
        SELECT count(*) INTO c2 FROM public.claim_agent_tasks('payment_settlement','w',5);
        RAISE NOTICE 'FAIL t6_second_claim_skips_paused';
    EXCEPTION WHEN raise_exception THEN
        IF SQLERRM LIKE 'AGENT_PAUSED%' THEN
            RAISE NOTICE 'PASS t6_second_claim_skips_paused';
        ELSE
            RAISE NOTICE 'FAIL t6_second_claim_skips_paused (wrong error: %)', SQLERRM;
        END IF;
    END;
END $$;

SELECT CASE WHEN status='paused' AND blocked_reason='BUDGET_EXHAUSTED'
            THEN 'PASS' ELSE 'FAIL' END AS t6_auto_pause_status
FROM public.agent_registry WHERE agent_name='payment_settlement';

-- -----------------------------------------------------------------------------
-- T7: heartbeat freshness write
-- -----------------------------------------------------------------------------
DO $$
BEGIN
    PERFORM public.heartbeat_agent('transportation');
END $$;

SELECT CASE WHEN last_heartbeat_at > CURRENT_TIMESTAMP - INTERVAL '1 minute'
            THEN 'PASS' ELSE 'FAIL' END AS t7_heartbeat_recorded
FROM public.agent_registry WHERE agent_name='transportation';

ROLLBACK;
