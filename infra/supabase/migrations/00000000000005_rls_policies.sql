-- M1: Row-Level Security policies
-- All policies assume auth.uid() matches users.user_id.

ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.customer_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.driver_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.transport_companies ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.vehicles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.vehicle_telemetry ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.order_event_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.payments ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.payment_transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.admin_actions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.driver_alerts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.notification_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.webhook_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.sop_sections ENABLE ROW LEVEL SECURITY;

-- Helper: is admin?
CREATE OR REPLACE FUNCTION public.is_admin()
RETURNS BOOLEAN AS $$
BEGIN
    RETURN EXISTS (
        SELECT 1 FROM public.users
        WHERE user_id = auth.uid() AND base_role = 'admin'
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- -----------------------------------------------------------------------------
-- users
-- -----------------------------------------------------------------------------
CREATE POLICY users_select_own_or_admin ON public.users
    FOR SELECT USING (user_id = auth.uid() OR public.is_admin());

CREATE POLICY users_update_own ON public.users
    FOR UPDATE USING (user_id = auth.uid()) WITH CHECK (user_id = auth.uid());

-- -----------------------------------------------------------------------------
-- customer_profiles
-- -----------------------------------------------------------------------------
CREATE POLICY customer_profiles_select_own_or_admin ON public.customer_profiles
    FOR SELECT USING (
        user_id = auth.uid() OR public.is_admin()
    );

CREATE POLICY customer_profiles_update_own ON public.customer_profiles
    FOR UPDATE USING (user_id = auth.uid()) WITH CHECK (user_id = auth.uid());

-- -----------------------------------------------------------------------------
-- driver_profiles
-- -----------------------------------------------------------------------------
CREATE POLICY driver_profiles_select_own_or_admin ON public.driver_profiles
    FOR SELECT USING (
        user_id = auth.uid() OR public.is_admin()
    );

CREATE POLICY driver_profiles_update_own ON public.driver_profiles
    FOR UPDATE USING (user_id = auth.uid()) WITH CHECK (user_id = auth.uid());

-- -----------------------------------------------------------------------------
-- transport_companies
-- -----------------------------------------------------------------------------
CREATE POLICY transport_companies_select_own_or_admin ON public.transport_companies
    FOR SELECT USING (
        user_id = auth.uid() OR public.is_admin()
    );

CREATE POLICY transport_companies_update_own ON public.transport_companies
    FOR UPDATE USING (user_id = auth.uid()) WITH CHECK (user_id = auth.uid());

-- -----------------------------------------------------------------------------
-- vehicles
-- -----------------------------------------------------------------------------
CREATE POLICY vehicles_select_own_or_admin ON public.vehicles
    FOR SELECT USING (
        owner_id = auth.uid() OR public.is_admin()
    );

CREATE POLICY vehicles_insert_own ON public.vehicles
    FOR INSERT WITH CHECK (owner_id = auth.uid());

CREATE POLICY vehicles_update_own ON public.vehicles
    FOR UPDATE USING (owner_id = auth.uid()) WITH CHECK (owner_id = auth.uid());

-- -----------------------------------------------------------------------------
-- vehicle_telemetry
-- -----------------------------------------------------------------------------
-- Open insert for authenticated service accounts; in production restrict to service-role key
CREATE POLICY vehicle_telemetry_insert_auth ON public.vehicle_telemetry
    FOR INSERT WITH CHECK (auth.role() = 'authenticated');

CREATE POLICY vehicle_telemetry_select_driver_or_owner_or_admin ON public.vehicle_telemetry
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM public.vehicles v
            WHERE v.vehicle_id = vehicle_telemetry.vehicle_id
              AND (v.owner_id = auth.uid() OR vehicle_telemetry.driver_id IN (
                  SELECT driver_id FROM public.driver_profiles WHERE user_id = auth.uid()
              ))
        )
        OR public.is_admin()
    );

-- -----------------------------------------------------------------------------
-- orders
-- -----------------------------------------------------------------------------
CREATE POLICY orders_select_customer_or_driver_or_company_or_admin ON public.orders
    FOR SELECT USING (
        customer_id IN (SELECT customer_id FROM public.customer_profiles WHERE user_id = auth.uid())
        OR driver_id IN (SELECT driver_id FROM public.driver_profiles WHERE user_id = auth.uid())
        OR transport_company_id IN (SELECT transport_company_id FROM public.transport_companies WHERE user_id = auth.uid())
        OR public.is_admin()
    );

CREATE POLICY orders_insert_customer ON public.orders
    FOR INSERT WITH CHECK (
        customer_id IN (SELECT customer_id FROM public.customer_profiles WHERE user_id = auth.uid())
    );

CREATE POLICY orders_update_customer_own_pending ON public.orders
    FOR UPDATE USING (
        customer_id IN (SELECT customer_id FROM public.customer_profiles WHERE user_id = auth.uid())
        AND order_status IN ('pending', 'inventory_confirmed')
    ) WITH CHECK (
        customer_id IN (SELECT customer_id FROM public.customer_profiles WHERE user_id = auth.uid())
    );

CREATE POLICY orders_update_driver_assigned ON public.orders
    FOR UPDATE USING (
        driver_id IN (SELECT driver_id FROM public.driver_profiles WHERE user_id = auth.uid())
    ) WITH CHECK (
        driver_id IN (SELECT driver_id FROM public.driver_profiles WHERE user_id = auth.uid())
    );

CREATE POLICY orders_update_company_assigned ON public.orders
    FOR UPDATE USING (
        transport_company_id IN (SELECT transport_company_id FROM public.transport_companies WHERE user_id = auth.uid())
    ) WITH CHECK (
        transport_company_id IN (SELECT transport_company_id FROM public.transport_companies WHERE user_id = auth.uid())
    );

-- -----------------------------------------------------------------------------
-- order_event_log
-- -----------------------------------------------------------------------------
CREATE POLICY order_event_log_select_related ON public.order_event_log
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM public.orders o
            WHERE o.order_id = order_event_log.order_id
              AND (o.customer_id IN (SELECT customer_id FROM public.customer_profiles WHERE user_id = auth.uid())
                   OR o.driver_id IN (SELECT driver_id FROM public.driver_profiles WHERE user_id = auth.uid())
                   OR o.transport_company_id IN (SELECT transport_company_id FROM public.transport_companies WHERE user_id = auth.uid())
                   OR public.is_admin())
        )
    );

-- -----------------------------------------------------------------------------
-- payments
-- -----------------------------------------------------------------------------
CREATE POLICY payments_select_related ON public.payments
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM public.orders o
            WHERE o.order_id = payments.order_id
              AND (o.customer_id IN (SELECT customer_id FROM public.customer_profiles WHERE user_id = auth.uid())
                   OR o.driver_id IN (SELECT driver_id FROM public.driver_profiles WHERE user_id = auth.uid())
                   OR o.transport_company_id IN (SELECT transport_company_id FROM public.transport_companies WHERE user_id = auth.uid())
                   OR public.is_admin())
        )
    );

-- -----------------------------------------------------------------------------
-- payment_transactions
-- -----------------------------------------------------------------------------
CREATE POLICY payment_transactions_select_related ON public.payment_transactions
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM public.orders o
            WHERE o.order_id = payment_transactions.order_id
              AND (o.customer_id IN (SELECT customer_id FROM public.customer_profiles WHERE user_id = auth.uid())
                   OR o.driver_id IN (SELECT driver_id FROM public.driver_profiles WHERE user_id = auth.uid())
                   OR o.transport_company_id IN (SELECT transport_company_id FROM public.transport_companies WHERE user_id = auth.uid())
                   OR public.is_admin())
        )
    );

-- -----------------------------------------------------------------------------
-- admin_actions
-- -----------------------------------------------------------------------------
CREATE POLICY admin_actions_select_admin ON public.admin_actions
    FOR SELECT USING (public.is_admin());

-- -----------------------------------------------------------------------------
-- driver_alerts
-- -----------------------------------------------------------------------------
CREATE POLICY driver_alerts_select_driver_or_admin ON public.driver_alerts
    FOR SELECT USING (
        driver_id IN (SELECT driver_id FROM public.driver_profiles WHERE user_id = auth.uid())
        OR public.is_admin()
    );

-- -----------------------------------------------------------------------------
-- notification_log
-- -----------------------------------------------------------------------------
CREATE POLICY notification_log_select_own ON public.notification_log
    FOR SELECT USING (user_id = auth.uid() OR public.is_admin());

CREATE POLICY notification_log_update_own ON public.notification_log
    FOR UPDATE USING (user_id = auth.uid()) WITH CHECK (user_id = auth.uid());

-- -----------------------------------------------------------------------------
-- webhook_events
-- -----------------------------------------------------------------------------
CREATE POLICY webhook_events_select_admin ON public.webhook_events
    FOR SELECT USING (public.is_admin());

-- -----------------------------------------------------------------------------
-- sop_sections
-- -----------------------------------------------------------------------------
CREATE POLICY sop_sections_select_all_auth ON public.sop_sections
    FOR SELECT USING (auth.role() = 'authenticated' OR public.is_admin());
