-- =============================================================================
-- M2 Migration 09: Payment-plan validation + payment-hold order guard
-- Rollback: DROP TRIGGER guard_payment_hold_on_order; DROP FUNCTION
--   enforce_payment_hold(); DROP FUNCTION validate_payment_plan(character,numeric,numeric);
-- =============================================================================

-- -----------------------------------------------------------------------------
-- validate_payment_plan — PRD modes with 50% partial floor
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.validate_payment_plan(
    p_mode            VARCHAR(20),   -- 'full' | 'partial' | 'to_pay'
    p_total_amount    NUMERIC,
    p_advance_amount  NUMERIC
)
RETURNS BOOLEAN AS $$
BEGIN
    IF p_total_amount IS NULL OR p_total_amount <= 0 THEN
        RAISE EXCEPTION 'INVALID_TOTAL_AMOUNT';
    END IF;
    IF p_mode NOT IN ('full','partial','to_pay') THEN
        RAISE EXCEPTION 'UNKNOWN_PAYMENT_MODE %', p_mode;
    END IF;

    IF p_mode = 'full' THEN
        IF p_advance_amount IS DISTINCT FROM p_total_amount THEN
            RAISE EXCEPTION 'FULL_MODE_REQUIRES_100_PCT_ADVANCE';
        END IF;
    ELSIF p_mode = 'partial' THEN
        IF p_advance_amount IS NULL OR p_advance_amount < (p_total_amount * 0.5) THEN
            RAISE EXCEPTION 'PARTIAL_MODE_MIN_50_PCT';
        END IF;
    ELSE -- to_pay: no advance at booking time
        IF COALESCE(p_advance_amount, 0) <> 0 THEN
            RAISE EXCEPTION 'TOPAY_MODE_NO_ADVANCE_ALLOWED';
        END IF;
    END IF;
    RETURN true;
END;
$$ LANGUAGE plpgsql STABLE;

-- -----------------------------------------------------------------------------
-- Admin override lookup: unexpired allow_user_with_pending_payment for a user
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.has_active_payment_hold_override(p_user_id UUID)
RETURNS BOOLEAN AS $$
DECLARE v_count INTEGER;
BEGIN
    SELECT count(*) INTO v_count
      FROM public.admin_actions a
     WHERE a.action_type = 'allow_user_with_pending_payment'
       AND a.target_type = 'user'
       AND a.target_id = p_user_id
       AND (a.expires_at IS NULL OR a.expires_at > CURRENT_TIMESTAMP);
    RETURN COALESCE(v_count, 0) > 0;
END;
$$ LANGUAGE plpgsql STABLE SECURITY DEFINER;

-- -----------------------------------------------------------------------------
-- BEFORE INSERT guard on orders — blocks held customers deterministically.
-- Service-role/owner inserts bypass RLS, so this trigger is the real fence.
-- customer_id references customer_profiles → user's payment_hold.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.enforce_payment_hold()
RETURNS TRIGGER AS $$
DECLARE v_user_id UUID;
BEGIN
    SELECT cp.user_id INTO v_user_id
      FROM public.customer_profiles cp
     WHERE cp.customer_id = NEW.customer_id;

    IF v_user_id IS NULL THEN
        RAISE EXCEPTION 'UNKNOWN_CUSTOMER_PROFILE %', NEW.customer_id;
    END IF;

    IF EXISTS (SELECT 1 FROM public.users u WHERE u.user_id = v_user_id AND u.payment_hold = true)
       AND NOT public.has_active_payment_hold_override(v_user_id) THEN
        RAISE EXCEPTION 'PAYMENT_HOLD_ACTIVE';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS guard_payment_hold_on_order ON public.orders;
CREATE TRIGGER guard_payment_hold_on_order
    BEFORE INSERT ON public.orders
    FOR EACH ROW EXECUTE FUNCTION public.enforce_payment_hold();
