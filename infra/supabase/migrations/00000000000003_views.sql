-- M1: Admin and operational views

-- -----------------------------------------------------------------------------
-- 1. Admin dashboard metrics
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW admin_dashboard_view AS
SELECT
    (SELECT COUNT(*) FROM public.users WHERE base_role = 'customer') AS total_customers,
    (SELECT COUNT(*) FROM public.users WHERE base_role = 'driver') AS total_drivers,
    (SELECT COUNT(*) FROM public.users WHERE base_role = 'transport_company') AS total_transport_companies,
    (SELECT COUNT(*) FROM public.orders WHERE order_status = 'pending') AS pending_orders,
    (SELECT COUNT(*) FROM public.orders WHERE order_status = 'in_transit') AS active_orders,
    (SELECT COUNT(*) FROM public.orders WHERE DATE(created_at) = CURRENT_DATE) AS orders_today,
    (SELECT COALESCE(SUM(total_amount), 0) FROM public.orders WHERE DATE(created_at) = CURRENT_DATE) AS revenue_today,
    (SELECT COUNT(*) FROM public.driver_alerts WHERE alert_status = 'active') AS active_alerts,
    (SELECT COUNT(*) FROM public.ai_agent_interventions WHERE DATE(detected_at) = CURRENT_DATE) AS ai_interventions_today,
    (SELECT COUNT(*) FROM public.admin_actions WHERE DATE(created_at) = CURRENT_DATE) AS admin_actions_today;

-- -----------------------------------------------------------------------------
-- 2. Transport company dual-role statistics
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW transport_company_role_stats AS
SELECT
    tc.transport_company_id,
    tc.company_name,
    u.active_role,
    COUNT(CASE WHEN o.transport_company_id = tc.transport_company_id AND o.order_status = 'delivered' THEN 1 END) AS orders_completed_as_provider,
    COUNT(CASE WHEN o.customer_id IN (SELECT customer_id FROM public.customer_profiles cp WHERE cp.user_id = tc.user_id) AND o.order_status = 'delivered' THEN 1 END) AS orders_completed_as_customer,
    COALESCE(SUM(CASE WHEN o.transport_company_id = tc.transport_company_id THEN o.commission_amount END), 0) AS total_commissions_paid,
    COALESCE(SUM(CASE WHEN o.customer_id IN (SELECT customer_id FROM public.customer_profiles cp WHERE cp.user_id = tc.user_id) THEN o.service_fee END), 0) AS total_service_fees_paid
FROM public.transport_companies tc
JOIN public.users u ON tc.user_id = u.user_id
LEFT JOIN public.orders o
    ON (o.transport_company_id = tc.transport_company_id
        OR o.customer_id IN (SELECT customer_id FROM public.customer_profiles cp WHERE cp.user_id = tc.user_id))
GROUP BY tc.transport_company_id, tc.company_name, u.active_role;

-- -----------------------------------------------------------------------------
-- 3. Driver earnings summary
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW driver_earnings_summary AS
SELECT
    dp.driver_id,
    u.first_name || ' ' || u.last_name AS driver_name,
    COUNT(CASE WHEN o.order_status = 'delivered' THEN 1 END) AS completed_orders,
    COALESCE(SUM(CASE WHEN o.order_status = 'delivered' THEN o.total_amount - o.commission_amount END), 0) AS total_earnings,
    COALESCE(SUM(CASE WHEN o.order_status = 'delivered' THEN o.commission_amount END), 0) AS total_commission
FROM public.driver_profiles dp
JOIN public.users u ON dp.user_id = u.user_id
LEFT JOIN public.orders o ON o.driver_id = dp.driver_id
GROUP BY dp.driver_id, u.first_name, u.last_name;
