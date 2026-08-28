-- =============================================================================
-- M3 Migration 10: Agent control plane â€” registry, task queue, pause/budget RPCs
-- D-17: paused / unfunded agents are skipped at CLAIM time, inside the DB.
-- Rollback: DROP TABLE agent_tasks; DROP TABLE agent_registry;
--   DROP FUNCTION claim_agent_tasks/complete_agent_task/fail_agent_task/
--   record_agent_spend/heartbeat_agent/register_agent(all overloads);
-- =============================================================================

CREATE TABLE IF NOT EXISTS public.agent_registry (
    agent_name             VARCHAR(50) PRIMARY KEY
        CHECK (agent_name IN ('customer_service','order_management','transportation',
                              'resource_management','payment_settlement',
                              'platform_administration','communication')),
    status                 VARCHAR(20) NOT NULL DEFAULT 'running'
                           CHECK (status IN ('running','paused','blocked')),
    daily_budget_usd_cents INTEGER NOT NULL DEFAULT 50000,
    budget_spent_cents     INTEGER NOT NULL DEFAULT 0 CHECK (budget_spent_cents >= 0),
    blocked_reason         TEXT,
    last_heartbeat_at      TIMESTAMPTZ,
    config                 JSONB NOT NULL DEFAULT '{}',
    created_at             TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at             TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_agent_registry_status ON public.agent_registry(status);

ALTER TABLE public.agent_registry ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS agent_registry_select_admin ON public.agent_registry;
CREATE POLICY agent_registry_select_admin ON public.agent_registry
    FOR SELECT USING (public.is_admin());
-- Workers use the service role which bypasses RLS; console admins get read.

-- -----------------------------------------------------------------------------
-- Durable task queue (idempotent via dedupe_key)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.agent_tasks (
    task_id       UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_name    VARCHAR(50) NOT NULL REFERENCES public.agent_registry(agent_name) ON DELETE CASCADE,
    task_type     VARCHAR(100) NOT NULL,
    payload       JSONB NOT NULL DEFAULT '{}',
    status        VARCHAR(20) NOT NULL DEFAULT 'queued'
                  CHECK (status IN ('queued','claimed','done','failed','dead')),
    priority      SMALLINT NOT NULL DEFAULT 5,
    attempts      SMALLINT NOT NULL DEFAULT 0,
    max_attempts  SMALLINT NOT NULL DEFAULT 3,
    claimed_by    TEXT,
    claimed_at    TIMESTAMPTZ,
    completed_at  TIMESTAMPTZ,
    result        JSONB,
    error         TEXT,
    dedupe_key    VARCHAR(150) UNIQUE,
    heartbeat_id  UUID,                     -- Â§16 correlation: trace root
    enqueued_by   VARCHAR(60),
    created_at    TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_agent_tasks_claim ON public.agent_tasks(agent_name, status, priority, created_at);
CREATE INDEX IF NOT EXISTS idx_agent_tasks_dedupe ON public.agent_tasks(dedupe_key) WHERE dedupe_key IS NOT NULL;

ALTER TABLE public.agent_tasks ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS agent_tasks_select_admin ON public.agent_tasks;
CREATE POLICY agent_tasks_select_admin ON public.agent_tasks FOR SELECT USING (public.is_admin());

-- -----------------------------------------------------------------------------
-- Registration helpers (idempotent)
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.register_agent(
    p_agent_name VARCHAR(50),
    p_budget_cents INTEGER DEFAULT NULL
)
RETURNS VOID AS $$
BEGIN
    INSERT INTO public.agent_registry AS r (agent_name, daily_budget_usd_cents)
    VALUES (p_agent_name, COALESCE(p_budget_cents, 50000))
    ON CONFLICT (agent_name) DO NOTHING;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION public.set_agent_status(p_agent_name VARCHAR(50), p_status VARCHAR(20), p_reason TEXT DEFAULT NULL)
RETURNS VOID AS $$
BEGIN
    UPDATE public.agent_registry
       SET status = p_status,
           blocked_reason = COALESCE(p_reason, CASE WHEN p_status = 'blocked' THEN blocked_reason ELSE NULL END),
           updated_at = CURRENT_TIMESTAMP
     WHERE agent_name = p_agent_name;
    IF NOT FOUND THEN RAISE EXCEPTION 'UNKNOWN_AGENT %', p_agent_name; END IF;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- -----------------------------------------------------------------------------
-- Claiming with D-17 skip semantics
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.claim_agent_tasks(
    p_agent_name VARCHAR(50),
    p_claimed_by TEXT,
    p_limit INTEGER DEFAULT 5,
    p_heartbeat_id UUID DEFAULT uuid_generate_v4()
)
RETURNS TABLE (
    task_id UUID, task_type VARCHAR(100), payload JSONB, attempts SMALLINT, heartbeat_id UUID
) AS $$
DECLARE
    v_registry public.agent_registry%ROWTYPE;
BEGIN
    SELECT * INTO v_registry FROM public.agent_registry ar WHERE ar.agent_name = p_agent_name;
    IF NOT FOUND THEN RAISE EXCEPTION 'UNKNOWN_AGENT %', p_agent_name; END IF;

    IF v_registry.status = 'paused' THEN
        RAISE EXCEPTION 'AGENT_PAUSED';
    ELSIF v_registry.status = 'blocked' THEN
        RAISE EXCEPTION 'AGENT_BLOCKED %', COALESCE(v_registry.blocked_reason,'unspecified');
    END IF;

    IF v_registry.budget_spent_cents >= v_registry.daily_budget_usd_cents THEN
        -- auto-pause on exhaustion so loops and human queues see one stable cause
        PERFORM public.set_agent_status(p_agent_name, 'paused', 'BUDGET_EXHAUSTED');
        RAISE EXCEPTION 'AGENT_BUDGET_EXHAUSTED';
    END IF;

    RETURN QUERY
    UPDATE public.agent_tasks t
       SET status='claimed', claimed_by=p_claimed_by, claimed_at=CURRENT_TIMESTAMP,
           attempts=t.attempts+1, heartbeat_id=p_heartbeat_id
     WHERE t.task_id IN (
          SELECT c.task_id FROM public.agent_tasks c
           WHERE c.agent_name = p_agent_name AND c.status='queued'
           ORDER BY c.priority ASC, c.created_at ASC
           LIMIT GREATEST(p_limit,1)
          FOR UPDATE SKIP LOCKED)
    RETURNING t.task_id, t.task_type, t.payload, t.attempts, p_heartbeat_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE OR REPLACE FUNCTION public.complete_agent_task(p_task_id UUID, p_result JSONB DEFAULT '{}')
RETURNS VOID AS $$
BEGIN
    UPDATE public.agent_tasks
       SET status='done', result=p_result, completed_at=CURRENT_TIMESTAMP
     WHERE task_id=p_task_id AND status='claimed';
    IF NOT FOUND THEN RAISE EXCEPTION 'TASK_NOT_IN_CLAIMED_STATE %', p_task_id; END IF;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE OR REPLACE FUNCTION public.fail_agent_task(p_task_id UUID, p_error TEXT)
RETURNS VOID AS $$
DECLARE v_max SMALLINT; v_att SMALLINT;
BEGIN
    SELECT max_attempts, attempts INTO v_max, v_att
      FROM public.agent_tasks WHERE task_id=p_task_id AND status='claimed'
      FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'TASK_NOT_IN_CLAIMED_STATE %', p_task_id; END IF;

    IF v_att >= v_max THEN
        UPDATE public.agent_tasks SET status='dead', error=LEFT(p_error,2000), completed_at=CURRENT_TIMESTAMP WHERE task_id=p_task_id;
    ELSE
        UPDATE public.agent_tasks SET status='queued', error=LEFT(p_error,2000) WHERE task_id=p_task_id;
    END IF;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE OR REPLACE FUNCTION public.record_agent_spend(p_agent_name VARCHAR(50), p_amount_cents INTEGER)
RETURNS INTEGER AS $$
DECLARE v_new INTEGER;
BEGIN
    IF p_amount_cents < 0 THEN RAISE EXCEPTION 'NEGATIVE_SPEND'; END IF;
    UPDATE public.agent_registry
       SET budget_spent_cents = budget_spent_cents + p_amount_cents,
           updated_at = CURRENT_TIMESTAMP
     WHERE agent_name = p_agent_name
     RETURNING budget_spent_cents INTO v_new;
    IF NOT FOUND THEN RAISE EXCEPTION 'UNKNOWN_AGENT %', p_agent_name; END IF;
    RETURN v_new;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE OR REPLACE FUNCTION public.heartbeat_agent(p_agent_name VARCHAR(50))
RETURNS VOID AS $$
BEGIN
    UPDATE public.agent_registry SET last_heartbeat_at=CURRENT_TIMESTAMP WHERE agent_name=p_agent_name;
    IF NOT FOUND THEN RAISE EXCEPTION 'UNKNOWN_AGENT %', p_agent_name; END IF;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Seed all seven agents
INSERT INTO public.agent_registry (agent_name) VALUES
    ('customer_service'),('order_management'),('transportation'),
    ('resource_management'),('payment_settlement'),
    ('platform_administration'),('communication')
ON CONFLICT (agent_name) DO NOTHING;
