-- =============================================================================
-- M2 Migration 08: Deterministic provider matching
-- D-05 contract: assignable identity returned is users.user_id
-- (same UUID space as orders.provider_id).
-- Rollback: DROP FUNCTION match_nearby_drivers(varchar, geography, numeric, integer);
-- =============================================================================

CREATE OR REPLACE FUNCTION public.match_nearby_drivers(
    p_pickup          GEOGRAPHY,
    p_radius_m        NUMERIC DEFAULT 50000,
    p_limit           INTEGER DEFAULT 10,
    p_required_class  VARCHAR(20) DEFAULT NULL,   -- vehicles.vehicle_type value or NULL=any
    p_cargo_weight_t  NUMERIC   DEFAULT NULL,     -- filters undersized vehicles when given
    p_body_type       VARCHAR(20) DEFAULT NULL,   -- 'Open Body'/'Closed Body'/NULL=any
    p_fuel_type       VARCHAR(30) DEFAULT NULL    -- preferred fuel type or NULL=any
)
RETURNS TABLE (
    user_id        UUID,        -- D-05: THIS is the assignment identity
    driver_id      UUID,
    driver_name    TEXT,
    rating         NUMERIC(2,1),
    vehicle_id     UUID,
    registration_number VARCHAR(50),
    vehicle_type   VARCHAR(20),
    capacity_tons  NUMERIC(5,2),
    model_name     TEXT,
    fuel_type      VARCHAR(30),
    gvw_tons       NUMERIC(6,2),
    distance_m     NUMERIC(12,1),
    score          NUMERIC(8,2),
    assigned_order_count INTEGER
) AS $$
BEGIN
    IF p_pickup IS NULL THEN
        RAISE EXCEPTION 'MISSING_PICKUP_LOCATION';
    END IF;
    IF p_radius_m IS NULL OR p_radius_m <= 0 THEN
        RAISE EXCEPTION 'INVALID_RADIUS';
    END IF;

    RETURN QUERY
    WITH candidates AS (
        SELECT
            u.user_id,
            dp.driver_id,
            u.first_name || ' ' || u.last_name       AS d_name,
            dp.rating,
            v.vehicle_id,
            v.registration_number,
            v.vehicle_type,
            v.capacity_tons,
            vm.model                                   AS model_name,
            vm.fuel_type,
            vm.gvw_tons,
            vm.body_type                               AS vm_body_type,
            ST_DDistance(v.current_location, p_pickup) AS dist_m
        FROM public.vehicles v
        JOIN public.users u
          ON u.user_id = v.owner_id                     -- personal-owner drivers
        JOIN public.driver_profiles dp
          ON dp.user_id = u.user_id
        LEFT JOIN public.vehicle_models vm
          ON vm.model_id = v.model_id
        WHERE v.current_status = 'online'
          AND v.is_active = true
          AND v.current_location IS NOT NULL
          AND (p_required_class IS NULL OR v.vehicle_type = p_required_class)
          AND (p_cargo_weight_t IS NULL
               OR v.capacity_tons >= p_cargo_weight_t)
          AND (p_body_type IS NULL
               OR v.body_type = p_body_type
               OR vm.body_type = p_body_type)
          AND (p_fuel_type IS NULL
               OR vm.fuel_type = p_fuel_type)
          AND ST_DWithin(v.current_location, p_pickup, p_radius_m)
    ),
    busy AS (
        SELECT o.driver_id AS b_did, count(*) AS b_orders
        FROM public.orders o
        WHERE o.order_status IN ('driver_assigned','in_transit')
        GROUP BY o.driver_id
    )
    SELECT
        c.user_id,
        c.driver_id,
        c.d_name,
        c.rating,
        c.vehicle_id,
        c.registration_number,
        c.vehicle_type,
        c.capacity_tons,
        c.model_name,
        c.fuel_type,
        c.gvw_tons,
        ROUND(c.dist_m::numeric, 1)                                       AS distance_m,
        ROUND((
            (c.rating * 10)
            - (c.dist_m / 1000.0) * 0.05
            + CASE WHEN c.vm_body_type IS NOT NULL THEN 1.0 ELSE 0.0 END   -- model-known bonus
        )::numeric, 2)                                                     AS score,
        COALESCE(b.b_orders, 0)::integer                                  AS assigned_order_count
    FROM candidates c
    LEFT JOIN busy b ON b.b_did = c.driver_id
    ORDER BY 12 DESC, 11 ASC, c.vehicle_id ASC;          -- deterministic: score, distance, id
END;
$$ LANGUAGE plpgsql STABLE SECURITY DEFINER;
