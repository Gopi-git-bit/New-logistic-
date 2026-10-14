-- =============================================================================
-- M2 Migration 07: Deterministic pricing engine
-- Rollback: DROP FUNCTION generate_order_quote(calculate_quote(infer_vehicle_class);
--          DROP TABLE pricing_toll_bands; DROP TABLE pricing_rate_bands;
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Reference data (single source of truth for every caller/agent)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.pricing_rate_bands (
    vehicle_class     VARCHAR(20) PRIMARY KEY CHECK (vehicle_class IN ('Mini Truck','LCV','MCV','HCV')),
    min_tons          NUMERIC(6,2) NOT NULL,
    max_tons          NUMERIC(6,2) NOT NULL,
    min_rate_per_km   NUMERIC(8,2) NOT NULL,
    max_rate_per_km   NUMERIC(8,2) NOT NULL,
    CONSTRAINT sane_band CHECK (min_tons < max_tons AND min_rate_per_km <= max_rate_per_km)
);

INSERT INTO public.pricing_rate_bands (vehicle_class, min_tons, max_tons, min_rate_per_km, max_rate_per_km) VALUES
    ('Mini Truck',  0.50,  2.00, 10.00, 25.00),
    ('LCV',         2.00,  7.00, 15.00, 40.00),
    ('MCV',         9.00, 12.00, 20.00, 30.00),
    ('HCV',        20.00, 40.00, 35.00, 85.00)
ON CONFLICT (vehicle_class) DO NOTHING;

-- Toll floors per PRD distance bands; max_km NULL = open-ended highest band
CREATE TABLE IF NOT EXISTS public.pricing_toll_bands (
    band_order  SMALLINT PRIMARY KEY,
    max_km      NUMERIC(10,2),
    toll_amount NUMERIC(10,2) NOT NULL
);

INSERT INTO public.pricing_toll_bands (band_order, max_km, toll_amount) VALUES
    (1,   50.00,   85.00),
    (2,  250.00,  415.00),
    (3,  800.00, 1575.00),
    (4,   NULL,  2600.00)
ON CONFLICT (band_order) DO NOTHING;

-- -----------------------------------------------------------------------------
-- Class inference: smallest class whose max_tons covers the weight
-- (deterministically resolves band gaps 7-9t and 12-20t upward)
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.infer_vehicle_class(p_weight_tons NUMERIC)
RETURNS VARCHAR(20) AS $$
DECLARE v_class VARCHAR(20);
BEGIN
    IF p_weight_tons IS NULL THEN
        RAISE EXCEPTION 'MISSING_CARGO_WEIGHT';
    END IF;
    IF p_weight_tons <= 0 THEN
        RAISE EXCEPTION 'INVALID_CARGO_WEIGHT';
    END IF;

    SELECT b.vehicle_class INTO v_class
      FROM public.pricing_rate_bands b
     WHERE p_weight_tons <= b.max_tons
     ORDER BY b.min_tons ASC
     LIMIT 1;

    IF v_class IS NULL THEN
        RAISE EXCEPTION 'CARGO_EXCEEDS_MAX_CAPACITY';   -- > 40 t
    END IF;
    RETURN v_class;
END;
$$ LANGUAGE plpgsql STABLE;

-- -----------------------------------------------------------------------------
-- Quote calculator — pure function, identical output for identical inputs
-- Mapping back to orders columns: base_amount = freight + toll + loading,
-- tax_amount = GST(5%) applied to that subtotal, total = base + tax.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.calculate_quote(
    p_vehicle_class VARCHAR(20),
    p_distance_km   NUMERIC,
    p_weight_tons   NUMERIC DEFAULT NULL
)
RETURNS TABLE (
    vehicle_class   VARCHAR(20),
    rate_per_km     NUMERIC(8,2),
    freight_amount  NUMERIC(10,2),
    toll_amount     NUMERIC(10,2),
    loading_amount  NUMERIC(10,2),
    tax_amount      NUMERIC(10,2),
    total_amount    NUMERIC(10,2)
) AS $$
DECLARE
    v_band        public.pricing_rate_bands%ROWTYPE;
    v_effective_w NUMERIC;
    v_rate        NUMERIC;
    v_freight     NUMERIC;
    v_toll        NUMERIC;
BEGIN
    IF p_distance_km IS NULL OR p_distance_km <= 0 THEN
        RAISE EXCEPTION 'INVALID_DISTANCE';
    END IF;

    SELECT * INTO v_band FROM public.pricing_rate_bands rb WHERE rb.vehicle_class = p_vehicle_class;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'UNKNOWN_VEHICLE_CLASS %', p_vehicle_class;
    END IF;

    -- Rate: interpolate by weight inside the band; NULL -> midpoint
    IF p_weight_tons IS NULL THEN
        v_rate := (v_band.min_rate_per_km + v_band.max_rate_per_km) / 2;
    ELSE
        IF p_weight_tons > v_band.max_tons THEN
            RAISE EXCEPTION 'CARGO_EXCEEDS_CLASS_CAPACITY %', p_vehicle_class;
        END IF;
        v_effective_w := GREATEST(v_band.min_tons, LEAST(v_band.max_tons, p_weight_tons));
        v_rate := v_band.min_rate_per_km
                + (v_effective_w - v_band.min_tons)
                  / (v_band.max_tons - v_band.min_tons)
                  * (v_band.max_rate_per_km - v_band.min_rate_per_km);
    END IF;

    v_freight := ROUND(v_rate * p_distance_km, 2);

    -- Toll: first band whose ceiling covers the distance (band 4 is open-ended)
    SELECT t.toll_amount INTO v_toll
      FROM public.pricing_toll_bands t
     WHERE t.max_km IS NULL OR p_distance_km <= t.max_km
     ORDER BY t.band_order ASC
     LIMIT 1;

    RETURN QUERY SELECT
        p_vehicle_class,
        ROUND(v_rate, 2) AS rate_per_km,
        v_freight,
        v_toll,
        ROUND(v_freight * 0.03, 2)                          AS loading_amount,
        ROUND((v_freight + v_toll + ROUND(v_freight * 0.03, 2)) * 0.05, 2) AS tax_amount,
        ROUND(v_freight + v_toll + ROUND(v_freight * 0.03, 2)
              + ROUND((v_freight + v_toll + ROUND(v_freight * 0.03, 2)) * 0.05, 2), 2) AS total_amount;
END;
$$ LANGUAGE plpgsql STABLE;

-- -----------------------------------------------------------------------------
-- Order-level quote: computes distance from geo points when missing,
-- persists amounts, emits traceable events. Only for pending orders.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.generate_order_quote(p_order_id UUID)
RETURNS TABLE (
    vehicle_class   VARCHAR(20),
    rate_per_km     NUMERIC(8,2),
    freight_amount  NUMERIC(10,2),
    toll_amount     NUMERIC(10,2),
    loading_amount  NUMERIC(10,2),
    tax_amount      NUMERIC(10,2),
    total_amount    NUMERIC(10,2)
) AS $$
DECLARE
    v_status     VARCHAR(30);
    v_weight     NUMERIC;
    v_pickup     GEOGRAPHY;
    v_delivery   GEOGRAPHY;
    v_dist       NUMERIC;
    v_class      VARCHAR(20);
    q            RECORD;
BEGIN
    SELECT o.order_status, o.cargo_weight, o.pickup_location, o.delivery_location
      INTO v_status, v_weight, v_pickup, v_delivery
      FROM public.orders o
     WHERE o.order_id = p_order_id
      FOR UPDATE;

    IF NOT FOUND THEN RAISE EXCEPTION 'ORDER_NOT_FOUND %', p_order_id; END IF;
    IF v_status <> 'pending' THEN
        RAISE EXCEPTION 'QUOTE_ONLY_FOR_PENDING_ORDERS';
    END IF;

    -- Distance: reuse stored estimate, else great-circle from locations
    v_dist := (SELECT o.estimated_distance FROM public.orders o WHERE o.order_id = p_order_id);
    IF (v_dist IS NULL OR v_dist <= 0) THEN
        IF v_pickup IS NULL OR v_delivery IS NULL THEN
            RAISE EXCEPTION 'MISSING_GEOLOCATIONS_FOR_DISTANCE';
        END IF;
        v_dist := ROUND(ST_Distance(v_pickup, v_delivery) / 1000.0, 2);
        UPDATE public.orders SET estimated_distance = v_dist WHERE order_id = p_order_id;
    END IF;

    v_class := public.infer_vehicle_class(v_weight);

    SELECT * INTO q FROM public.calculate_quote(v_class, v_dist, v_weight);

    UPDATE public.orders
       SET base_amount  = q.freight_amount + q.toll_amount + q.loading_amount,
           tax_amount   = q.tax_amount,
           total_amount = q.total_amount
     WHERE order_id = p_order_id;

    INSERT INTO public.order_event_log (order_id, event_type, source, payload)
    VALUES (p_order_id, 'order_quote_generated', 'system',
        jsonb_build_object(
            'vehicle_class', q.vehicle_class,
            'distance_km',   v_dist,
            'weight_tons',   v_weight,
            'rate_per_km',   q.rate_per_km,
            'freight',       q.freight_amount,
            'toll',          q.toll_amount,
            'loading_3pct',  q.loading_amount,
            'gst_5pct',      q.tax_amount,
            'total',         q.total_amount
        ));

    RETURN QUERY SELECT q.vehicle_class, q.rate_per_km, q.freight_amount,
                        q.toll_amount, q.loading_amount, q.tax_amount, q.total_amount;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
