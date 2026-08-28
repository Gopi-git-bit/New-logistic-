-- M1: Functions and triggers

-- -----------------------------------------------------------------------------
-- 1. Generic updated_at trigger
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$
DECLARE
    t text;
BEGIN
    FOR t IN
        SELECT tablename FROM pg_tables
        WHERE schemaname = 'public'
          AND tablename IN (
              'users', 'customer_profiles', 'driver_profiles', 'transport_companies',
              'vehicles', 'orders', 'payments', 'payment_transactions'
          )
    LOOP
        EXECUTE format('DROP TRIGGER IF EXISTS trg_%I_set_updated_at ON public.%I;', t, t);
        EXECUTE format('CREATE TRIGGER trg_%I_set_updated_at BEFORE UPDATE ON public.%I FOR EACH ROW EXECUTE FUNCTION set_updated_at();', t, t);
    END LOOP;
END;
$$;

-- -----------------------------------------------------------------------------
-- 2. Order state machine: SECURITY DEFINER transition function
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION transition_order(
    p_order_id UUID,
    p_new_status VARCHAR(30),
    p_actor_id UUID DEFAULT NULL,
    p_actor_role VARCHAR(20) DEFAULT 'system',
    p_reason TEXT DEFAULT NULL
)
RETURNS TABLE (
    order_id UUID,
    old_status VARCHAR(30),
    new_status VARCHAR(30),
    changed_at TIMESTAMPTZ
) AS $$
DECLARE
    v_old_status VARCHAR(30);
    v_allowed BOOLEAN := false;
    v_customer_id UUID;
    v_driver_id UUID;
    v_company_id UUID;
BEGIN
    -- Lock the row
    SELECT o.order_status, o.customer_id, o.driver_id, o.transport_company_id
      INTO v_old_status, v_customer_id, v_driver_id, v_company_id
      FROM public.orders o
     WHERE o.order_id = p_order_id
      FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Order % not found', p_order_id;
    END IF;

    -- Same status is idempotent
    IF v_old_status = p_new_status THEN
        RETURN QUERY SELECT p_order_id, v_old_status, p_new_status, CURRENT_TIMESTAMP;
        RETURN;
    END IF;

    -- Validate actor permission (simplified; RLS is the primary gate)
    IF p_actor_role = 'system' OR p_actor_role = 'admin' THEN
        v_allowed := true;
    ELSIF p_actor_role = 'customer' AND v_customer_id = p_actor_id THEN
        v_allowed := true;
    ELSIF p_actor_role = 'driver' AND v_driver_id = p_actor_id THEN
        v_allowed := true;
    ELSIF p_actor_role = 'transport_company' AND v_company_id = p_actor_id THEN
        v_allowed := true;
    END IF;

    IF NOT v_allowed THEN
        RAISE EXCEPTION 'Actor % with role % is not authorized to transition order %', p_actor_id, p_actor_role, p_order_id;
    END IF;

    -- Validate transition
    IF v_old_status = 'pending' AND p_new_status IN ('inventory_confirmed', 'cancelled') THEN
        v_allowed := true;
    ELSIF v_old_status = 'inventory_confirmed' AND p_new_status IN ('payment_succeeded', 'cancelled') THEN
        v_allowed := true;
    ELSIF v_old_status = 'payment_succeeded' AND p_new_status IN ('driver_assigned', 'cancelled') THEN
        v_allowed := true;
    ELSIF v_old_status = 'driver_assigned' AND p_new_status IN ('in_transit', 'cancelled') THEN
        v_allowed := true;
    ELSIF v_old_status = 'in_transit' AND p_new_status IN ('delivered', 'cancelled') THEN
        v_allowed := true;
    ELSIF v_old_status = 'delivered' AND p_new_status IN ('payment_settled', 'cancelled') THEN
        v_allowed := true;
    ELSE
        v_allowed := false;
    END IF;

    IF NOT v_allowed THEN
        RAISE EXCEPTION 'Invalid transition from % to % for order %', v_old_status, p_new_status, p_order_id;
    END IF;

    -- Apply transition
    UPDATE public.orders
       SET previous_status = order_status,
           order_status = p_new_status,
           status_changed_at = CURRENT_TIMESTAMP,
           status_changed_by = p_actor_id,
           cancellation_reason = CASE WHEN p_new_status = 'cancelled' THEN p_reason ELSE cancellation_reason END,
           cancelled_at = CASE WHEN p_new_status = 'cancelled' THEN CURRENT_TIMESTAMP ELSE cancelled_at END,
           cancelled_by = CASE WHEN p_new_status = 'cancelled' THEN p_actor_id ELSE cancelled_by END
     WHERE public.orders.order_id = p_order_id;

    -- Log event
    INSERT INTO public.order_event_log (order_id, event_type, payload, source, emitted_by)
    VALUES (
        p_order_id,
        'order_status_changed',
        jsonb_build_object(
            'old_status', v_old_status,
            'new_status', p_new_status,
            'actor_role', p_actor_role,
            'reason', p_reason
        ),
        'system',
        p_actor_id
    );

    RETURN QUERY SELECT p_order_id, v_old_status, p_new_status, CURRENT_TIMESTAMP;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- -----------------------------------------------------------------------------
-- 3. Commission / service-fee calculation
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION calculate_commission()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.provider_type = 'driver' THEN
        NEW.commission_rate := 0.10;
        NEW.commission_amount := NEW.total_amount * NEW.commission_rate;
        NEW.service_fee := 0.00;
        NEW.service_fee_rate := 0.00;
    ELSIF NEW.provider_type = 'transport_company' THEN
        NEW.commission_rate := 0.00;
        NEW.commission_amount := 0.00;
        NEW.service_fee := 700.00;
        NEW.service_fee_rate := 0.00;
    ELSE
        NEW.commission_rate := 0.00;
        NEW.commission_amount := 0.00;
        NEW.service_fee := 0.00;
        NEW.service_fee_rate := 0.00;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_calculate_commission ON public.orders;
CREATE TRIGGER trigger_calculate_commission
    BEFORE INSERT OR UPDATE OF provider_type, total_amount ON public.orders
    FOR EACH ROW EXECUTE FUNCTION calculate_commission();

-- -----------------------------------------------------------------------------
-- 4. Payment transaction recording
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION record_payment_transaction()
RETURNS TRIGGER AS $$
BEGIN
    -- Record main payment transaction
    INSERT INTO public.payment_transactions (
        order_id, payment_id, transaction_type, amount, transaction_status, gateway_transaction_id, gateway_response, processed_at
    ) VALUES (
        NEW.order_id,
        NEW.payment_id,
        'payment',
        NEW.amount,
        NEW.payment_status,
        NEW.gateway_payment_id,
        NEW.gateway_response,
        NEW.processed_at
    );

    -- Commission transaction if applicable
    IF EXISTS (
        SELECT 1 FROM public.orders o
        WHERE o.order_id = NEW.order_id AND o.provider_type = 'driver' AND o.commission_amount > 0
    ) THEN
        INSERT INTO public.payment_transactions (
            order_id, transaction_type, amount, transaction_status, processed_at
        ) VALUES (
            NEW.order_id,
            'commission',
            (SELECT o.commission_amount FROM public.orders o WHERE o.order_id = NEW.order_id),
            'completed',
            NEW.processed_at
        );
    END IF;

    -- Service fee transaction if applicable
    IF EXISTS (
        SELECT 1 FROM public.orders o
        WHERE o.order_id = NEW.order_id AND o.provider_type = 'transport_company' AND o.service_fee > 0
    ) THEN
        INSERT INTO public.payment_transactions (
            order_id, transaction_type, amount, transaction_status, processed_at
        ) VALUES (
            NEW.order_id,
            'service_fee',
            (SELECT o.service_fee FROM public.orders o WHERE o.order_id = NEW.order_id),
            'completed',
            NEW.processed_at
        );
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_record_payment_transaction ON public.payments;
CREATE TRIGGER trigger_record_payment_transaction
    AFTER INSERT OR UPDATE OF payment_status ON public.payments
    FOR EACH ROW
    WHEN (NEW.payment_status = 'completed')
    EXECUTE FUNCTION record_payment_transaction();

-- -----------------------------------------------------------------------------
-- 5. Driver long-halt detection
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION detect_driver_long_halt()
RETURNS TRIGGER AS $$
DECLARE
    last_location RECORD;
    halt_duration INTERVAL;
    v_driver_id UUID;
BEGIN
    -- Attribute the alert to a driver:
    -- 1) telemetry row's own driver_id, 2) vehicle's assigned driver, 3) owner's driver profile
    v_driver_id := NEW.driver_id;

    IF v_driver_id IS NULL THEN
        SELECT assigned_driver_id INTO v_driver_id
          FROM public.vehicles
         WHERE vehicle_id = NEW.vehicle_id;
    END IF;

    IF v_driver_id IS NULL THEN
        SELECT dp.driver_id INTO v_driver_id
          FROM public.driver_profiles dp
          JOIN public.vehicles v ON v.owner_id = dp.user_id
         WHERE v.vehicle_id = NEW.vehicle_id
         LIMIT 1;
    END IF;

    -- Previous location (skip current row). Use FOUND: composite
    -- "IS NOT NULL" would be false whenever any telemetry column is NULL.
    SELECT *
      INTO last_location
      FROM public.vehicle_telemetry
     WHERE vehicle_id = NEW.vehicle_id
       AND telemetry_id != NEW.telemetry_id
     ORDER BY recorded_at DESC
     LIMIT 1;

    IF FOUND THEN
        halt_duration := NEW.recorded_at - last_location.recorded_at;

        IF halt_duration > INTERVAL '30 minutes'
           AND ST_Distance(
               ST_SetSRID(ST_MakePoint(NEW.longitude, NEW.latitude), 4326)::geography,
               ST_SetSRID(ST_MakePoint(last_location.longitude, last_location.latitude), 4326)::geography
           ) < 100
           AND v_driver_id IS NOT NULL THEN
            INSERT INTO public.driver_alerts (
                driver_id, vehicle_id, alert_type, latitude, longitude, alert_details
            ) VALUES (
                v_driver_id,
                NEW.vehicle_id,
                'long_halt',
                NEW.latitude,
                NEW.longitude,
                jsonb_build_object(
                    'halt_duration', halt_duration::text,
                    'last_location_timestamp', last_location.recorded_at
                )
            );
        END IF;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_detect_driver_long_halt ON public.vehicle_telemetry;
CREATE TRIGGER trigger_detect_driver_long_halt
    AFTER INSERT ON public.vehicle_telemetry
    FOR EACH ROW EXECUTE FUNCTION detect_driver_long_halt();

-- -----------------------------------------------------------------------------
-- 6. Order assignment helper
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION assign_order_provider(
    p_order_id UUID,
    p_provider_id UUID,
    p_provider_type VARCHAR(20)
)
RETURNS VOID AS $$
DECLARE
    v_driver_id UUID;
    v_company_id UUID;
BEGIN
    IF p_provider_type = 'driver' THEN
        SELECT driver_id INTO v_driver_id FROM public.driver_profiles WHERE user_id = p_provider_id;
        UPDATE public.orders
           SET provider_id = p_provider_id,
               provider_type = 'driver',
               driver_id = v_driver_id,
               transport_company_id = NULL,
               assigned_at = CURRENT_TIMESTAMP
         WHERE order_id = p_order_id;
    ELSIF p_provider_type = 'transport_company' THEN
        SELECT transport_company_id INTO v_company_id FROM public.transport_companies WHERE user_id = p_provider_id;
        UPDATE public.orders
           SET provider_id = p_provider_id,
               provider_type = 'transport_company',
               transport_company_id = v_company_id,
               driver_id = NULL,
               assigned_at = CURRENT_TIMESTAMP
         WHERE order_id = p_order_id;
    ELSE
        RAISE EXCEPTION 'Invalid provider_type %', p_provider_type;
    END IF;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
