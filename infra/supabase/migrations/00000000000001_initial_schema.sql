-- M1: Initial schema for Zippy Logistics v2 control plane

-- -----------------------------------------------------------------------------
-- 1. Unified identity
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    user_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    phone_number VARCHAR(20) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    base_role VARCHAR(20) NOT NULL CHECK (base_role IN ('customer', 'driver', 'transport_company', 'admin')),
    active_role VARCHAR(20) DEFAULT NULL CHECK (active_role IN ('customer', 'provider')),
    is_active BOOLEAN DEFAULT true,
    email_verified BOOLEAN DEFAULT false,
    phone_verified BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMPTZ,
    profile_image_url VARCHAR(500),
    preferred_language VARCHAR(10) DEFAULT 'en',
    payment_hold BOOLEAN DEFAULT false,
    payment_hold_reason TEXT,
    CONSTRAINT valid_email CHECK (email ~* '^[A-Za-z0-9._%-]+@[A-Za-z0-9.-]+[.][A-Za-z]+$'),
    CONSTRAINT valid_phone CHECK (phone_number ~* '^[0-9]{10}$'),
    CONSTRAINT valid_role_combination CHECK (
        (base_role != 'transport_company')
        OR (base_role = 'transport_company' AND active_role IN ('customer', 'provider', NULL))
    )
);

CREATE INDEX idx_users_base_role ON users(base_role);
CREATE INDEX idx_users_active_role ON users(active_role);
CREATE INDEX idx_users_payment_hold ON users(payment_hold) WHERE payment_hold = true;

-- -----------------------------------------------------------------------------
-- 2. Customer profiles
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS customer_profiles (
    customer_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    company_name VARCHAR(255),
    customer_category VARCHAR(20) CHECK (customer_category IN ('MSME', 'Warehouse', 'Enterprise')),
    gst_pan_number VARCHAR(50),
    company_phone VARCHAR(20),
    company_email VARCHAR(255),
    verification_status VARCHAR(20) DEFAULT 'pending' CHECK (verification_status IN ('pending', 'verified', 'rejected')),
    kyc_documents JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT valid_company_email CHECK (company_email IS NULL OR company_email ~* '^[A-Za-z0-9._%-]+@[A-Za-z0-9.-]+[.][A-Za-z]+$')
);

CREATE INDEX idx_customer_profiles_user_id ON customer_profiles(user_id);

-- -----------------------------------------------------------------------------
-- 3. Driver profiles
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS driver_profiles (
    driver_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    date_of_birth DATE,
    years_of_experience INTEGER DEFAULT 0,
    driver_status VARCHAR(30) CHECK (driver_status IN ('Salaried Driver', 'Vehicle Owner')),
    license_number VARCHAR(100),
    license_verified BOOLEAN DEFAULT false,
    rating DECIMAL(2,1) DEFAULT 5.0 CHECK (rating >= 1.0 AND rating <= 5.0),
    documents JSONB DEFAULT '{}',
    bank_account JSONB DEFAULT '{}',
    emergency_contact JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_driver_profiles_user_id ON driver_profiles(user_id);

-- -----------------------------------------------------------------------------
-- 4. Transport companies
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS transport_companies (
    transport_company_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    company_name VARCHAR(255) NOT NULL,
    gst_number VARCHAR(50),
    pan_number VARCHAR(50),
    service_areas TEXT[],
    specializations TEXT[],
    reliability_score DECIMAL(3,2) DEFAULT 0.00,
    is_verified BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_transport_companies_user_id ON transport_companies(user_id);

-- -----------------------------------------------------------------------------
-- 5. Vehicles
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS vehicle_models (
    model_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    brand VARCHAR(100),
    model VARCHAR(100) NOT NULL,
    vehicle_type VARCHAR(20) NOT NULL CHECK (vehicle_type IN ('LCV', 'MCV', 'HCV', 'Mini Truck')),
    body_type VARCHAR(20) CHECK (body_type IN ('Open Body', 'Closed Body')),
    capacity_tons DECIMAL(5,2),
    length_ft DECIMAL(5,2),
    width_ft DECIMAL(5,2),
    height_ft DECIMAL(5,2),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS vehicles (
    vehicle_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    owner_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    model_id UUID REFERENCES vehicle_models(model_id) ON DELETE SET NULL,
    assigned_driver_id UUID REFERENCES driver_profiles(driver_id) ON DELETE SET NULL,
    registration_number VARCHAR(50) UNIQUE NOT NULL,
    vehicle_type VARCHAR(20) NOT NULL CHECK (vehicle_type IN ('LCV', 'MCV', 'HCV', 'Mini Truck')),
    body_type VARCHAR(20) CHECK (body_type IN ('Open Body', 'Closed Body')),
    capacity_tons DECIMAL(5,2),
    current_status VARCHAR(20) DEFAULT 'offline' CHECK (current_status IN ('online', 'offline', 'in_transition', 'maintenance')),
    current_location GEOGRAPHY(POINT,4326),
    last_seen_at TIMESTAMPTZ,
    is_active BOOLEAN DEFAULT true,
    ownership_type VARCHAR(20) DEFAULT 'personal' CHECK (ownership_type IN ('personal', 'company')),
    documents JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_vehicles_owner_id ON vehicles(owner_id);
CREATE INDEX idx_vehicles_status ON vehicles(current_status);
CREATE INDEX idx_vehicles_location ON vehicles USING GIST(current_location);

-- -----------------------------------------------------------------------------
-- 6. Vehicle telemetry
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS vehicle_telemetry (
    telemetry_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    vehicle_id UUID NOT NULL REFERENCES vehicles(vehicle_id) ON DELETE CASCADE,
    driver_id UUID REFERENCES driver_profiles(driver_id) ON DELETE SET NULL,
    latitude DECIMAL(10,8) NOT NULL,
    longitude DECIMAL(11,8) NOT NULL,
    speed_kmph DECIMAL(5,2),
    heading DECIMAL(5,2),
    location GEOGRAPHY(POINT,4326),
    recorded_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX idx_vehicle_telemetry_vehicle_id ON vehicle_telemetry(vehicle_id, recorded_at DESC);
CREATE INDEX idx_vehicle_telemetry_location ON vehicle_telemetry USING GIST(location);

-- -----------------------------------------------------------------------------
-- 7. Orders
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS orders (
    order_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    order_number VARCHAR(20) UNIQUE NOT NULL,
    customer_id UUID NOT NULL REFERENCES customer_profiles(customer_id) ON DELETE CASCADE,
    provider_id UUID,
    provider_type VARCHAR(20) CHECK (provider_type IN ('driver', 'transport_company')),
    driver_id UUID REFERENCES driver_profiles(driver_id) ON DELETE SET NULL,
    transport_company_id UUID REFERENCES transport_companies(transport_company_id) ON DELETE SET NULL,
    vehicle_id UUID REFERENCES vehicles(vehicle_id) ON DELETE SET NULL,
    order_status VARCHAR(30) DEFAULT 'pending' CHECK (order_status IN (
        'pending', 'inventory_confirmed', 'payment_succeeded', 'driver_assigned',
        'in_transit', 'delivered', 'cancelled', 'payment_settled'
    )),
    previous_status VARCHAR(30),
    status_changed_at TIMESTAMPTZ,
    status_changed_by UUID REFERENCES users(user_id) ON DELETE SET NULL,

    -- Locations
    pickup_address_line1 VARCHAR(200) NOT NULL,
    pickup_address_line2 VARCHAR(200),
    pickup_city VARCHAR(100) NOT NULL,
    pickup_state VARCHAR(100) NOT NULL,
    pickup_postal_code VARCHAR(20) NOT NULL,
    pickup_latitude DECIMAL(10,8),
    pickup_longitude DECIMAL(11,8),
    pickup_location GEOGRAPHY(POINT,4326),

    delivery_address_line1 VARCHAR(200) NOT NULL,
    delivery_address_line2 VARCHAR(200),
    delivery_city VARCHAR(100) NOT NULL,
    delivery_state VARCHAR(100) NOT NULL,
    delivery_postal_code VARCHAR(20) NOT NULL,
    delivery_latitude DECIMAL(10,8),
    delivery_longitude DECIMAL(11,8),
    delivery_location GEOGRAPHY(POINT,4326),

    -- Consignee
    consignee_name VARCHAR(100) NOT NULL,
    consignee_phone VARCHAR(20) NOT NULL,
    consignee_email VARCHAR(255),

    -- Cargo
    cargo_description TEXT,
    cargo_weight DECIMAL(8,2),
    cargo_volume DECIMAL(8,2),
    special_instructions TEXT,
    special_requirements TEXT[],

    -- Timing
    scheduled_pickup_time TIMESTAMPTZ,
    scheduled_delivery_time TIMESTAMPTZ,
    actual_pickup_time TIMESTAMPTZ,
    actual_delivery_time TIMESTAMPTZ,

    -- Route
    estimated_distance DECIMAL(8,2),
    estimated_duration INTEGER,
    route_polyline TEXT,

    -- Pricing
    base_amount DECIMAL(10,2) NOT NULL,
    tax_amount DECIMAL(10,2) DEFAULT 0.00,
    total_amount DECIMAL(10,2) NOT NULL,
    commission_amount DECIMAL(10,2) DEFAULT 0.00,
    commission_rate DECIMAL(5,4) DEFAULT 0.00,
    service_fee DECIMAL(10,2) DEFAULT 0.00,
    service_fee_rate DECIMAL(5,4) DEFAULT 0.00,
    cancellation_fee DECIMAL(10,2) DEFAULT 0.00,

    -- Payment
    payment_status VARCHAR(20) DEFAULT 'pending' CHECK (payment_status IN ('pending', 'processing', 'completed', 'failed', 'cancelled', 'refunded', 'partial')),
    payment_method VARCHAR(50),
    payment_mode VARCHAR(20) DEFAULT 'full' CHECK (payment_mode IN ('full', 'partial', 'to_pay')),

    -- Cancellation
    cancellation_reason TEXT,
    cancelled_at TIMESTAMPTZ,
    cancelled_by UUID REFERENCES users(user_id) ON DELETE SET NULL,

    -- Assignment
    assigned_at TIMESTAMPTZ,
    assigned_by UUID REFERENCES users(user_id) ON DELETE SET NULL,

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT positive_amounts CHECK (base_amount > 0 AND total_amount > 0),
    CONSTRAINT valid_cancellation CHECK (
        (order_status != 'cancelled')
        OR (order_status = 'cancelled' AND cancellation_reason IS NOT NULL AND cancelled_at IS NOT NULL)
    ),
    CONSTRAINT valid_provider_assignment CHECK (
        (provider_type = 'driver' AND driver_id IS NOT NULL AND transport_company_id IS NULL)
        OR (provider_type = 'transport_company' AND transport_company_id IS NOT NULL)
        OR (provider_type IS NULL)
    )
);

CREATE INDEX idx_orders_customer_id ON orders(customer_id);
CREATE INDEX idx_orders_driver_id ON orders(driver_id);
CREATE INDEX idx_orders_transport_company_id ON orders(transport_company_id);
CREATE INDEX idx_orders_status ON orders(order_status);
CREATE INDEX idx_orders_created_at ON orders(created_at);
CREATE INDEX idx_orders_pickup_location ON orders USING GIST(pickup_location);
CREATE INDEX idx_orders_delivery_location ON orders USING GIST(delivery_location);

-- -----------------------------------------------------------------------------
-- 8. Order event log
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS order_event_log (
    event_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    order_id UUID NOT NULL REFERENCES orders(order_id) ON DELETE CASCADE,
    event_type VARCHAR(100) NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}',
    source VARCHAR(50) NOT NULL CHECK (source IN ('customer_app', 'admin_panel', 'driver_app', 'transport_app', 'worker', 'system')),
    emitted_by UUID REFERENCES users(user_id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_order_event_log_order_id ON order_event_log(order_id, created_at DESC);
CREATE INDEX idx_order_event_log_type ON order_event_log(event_type);

-- -----------------------------------------------------------------------------
-- 9. Payments
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS payments (
    payment_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    order_id UUID NOT NULL REFERENCES orders(order_id) ON DELETE CASCADE,
    amount DECIMAL(10,2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'INR',
    payment_status VARCHAR(20) DEFAULT 'pending' CHECK (payment_status IN ('pending', 'processing', 'completed', 'failed', 'cancelled', 'refunded')),
    payment_method VARCHAR(50),
    payment_gateway VARCHAR(20) CHECK (payment_gateway IN ('razorpay', 'stripe', 'paypal', 'cash')),
    gateway_payment_id VARCHAR(100),
    gateway_response JSONB DEFAULT '{}',
    processed_at TIMESTAMPTZ,
    idempotency_key VARCHAR(100) UNIQUE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT positive_payment CHECK (amount > 0)
);

CREATE INDEX idx_payments_order_id ON payments(order_id);
CREATE INDEX idx_payments_status ON payments(payment_status);
CREATE INDEX idx_payments_idempotency ON payments(idempotency_key);

-- -----------------------------------------------------------------------------
-- 10. Payment transactions
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS payment_transactions (
    transaction_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    order_id UUID NOT NULL REFERENCES orders(order_id) ON DELETE CASCADE,
    payment_id UUID REFERENCES payments(payment_id) ON DELETE SET NULL,
    transaction_type VARCHAR(20) NOT NULL CHECK (transaction_type IN ('payment', 'refund', 'commission', 'service_fee')),
    amount DECIMAL(10,2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'INR',
    transaction_status VARCHAR(20) DEFAULT 'pending' CHECK (transaction_status IN ('pending', 'processing', 'completed', 'failed')),
    gateway_transaction_id VARCHAR(100),
    gateway_response JSONB DEFAULT '{}',
    processed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT positive_transaction CHECK (amount > 0)
);

CREATE INDEX idx_payment_transactions_order_id ON payment_transactions(order_id);
CREATE INDEX idx_payment_transactions_type ON payment_transactions(transaction_type);

-- -----------------------------------------------------------------------------
-- 11. Admin actions
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS admin_actions (
    action_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    admin_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    action_type VARCHAR(50) NOT NULL CHECK (action_type IN (
        'suppress_alert', 'allow_user_with_pending_payment', 'cancel_suspicious_order',
        'suspend_user', 'lift_suspension', 'override_system', 'regulate_ai_agent'
    )),
    target_type VARCHAR(20) NOT NULL CHECK (target_type IN ('user', 'order', 'alert', 'ai_agent')),
    target_id UUID,
    action_details JSONB DEFAULT '{}',
    reason TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMPTZ
);

CREATE INDEX idx_admin_actions_admin_id ON admin_actions(admin_id, created_at DESC);
CREATE INDEX idx_admin_actions_target ON admin_actions(target_type, target_id);

-- -----------------------------------------------------------------------------
-- 12. Driver alerts
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS driver_alerts (
    alert_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    driver_id UUID NOT NULL REFERENCES driver_profiles(driver_id) ON DELETE CASCADE,
    vehicle_id UUID REFERENCES vehicles(vehicle_id) ON DELETE SET NULL,
    order_id UUID REFERENCES orders(order_id) ON DELETE SET NULL,
    alert_type VARCHAR(50) NOT NULL CHECK (alert_type IN ('long_halt', 'route_deviation', 'breakdown', 'accident')),
    alert_status VARCHAR(20) DEFAULT 'active' CHECK (alert_status IN ('active', 'acknowledged', 'suppressed', 'resolved')),
    latitude DECIMAL(10,8),
    longitude DECIMAL(11,8),
    alert_details JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    acknowledged_at TIMESTAMPTZ,
    acknowledged_by UUID REFERENCES users(user_id) ON DELETE SET NULL,
    suppressed_at TIMESTAMPTZ,
    suppressed_by UUID REFERENCES users(user_id) ON DELETE SET NULL,
    resolved_at TIMESTAMPTZ,
    resolved_by UUID REFERENCES users(user_id) ON DELETE SET NULL
);

CREATE INDEX idx_driver_alerts_driver_id ON driver_alerts(driver_id);
CREATE INDEX idx_driver_alerts_status ON driver_alerts(alert_status);
CREATE INDEX idx_driver_alerts_created_at ON driver_alerts(created_at DESC);

-- -----------------------------------------------------------------------------
-- 13. AI agent observability
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ai_agent_activities (
    activity_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_name VARCHAR(50) NOT NULL,
    agent_type VARCHAR(50) NOT NULL,
    activity_type VARCHAR(50) NOT NULL,
    activity_details JSONB DEFAULT '{}',
    input_data JSONB DEFAULT '{}',
    output_data JSONB DEFAULT '{}',
    confidence_score DECIMAL(5,4),
    execution_time_ms INTEGER,
    status VARCHAR(20) DEFAULT 'completed' CHECK (status IN ('pending', 'completed', 'failed', 'interrupted')),
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    order_id UUID REFERENCES orders(order_id) ON DELETE SET NULL,
    user_id UUID REFERENCES users(user_id) ON DELETE SET NULL
);

CREATE INDEX idx_ai_agent_activities_agent ON ai_agent_activities(agent_name, created_at DESC);
CREATE INDEX idx_ai_agent_activities_order ON ai_agent_activities(order_id);

CREATE TABLE IF NOT EXISTS ai_agent_interventions (
    intervention_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_name VARCHAR(50) NOT NULL,
    intervention_type VARCHAR(50) NOT NULL CHECK (intervention_type IN ('hallucination', 'error_correction', 'performance_issue', 'anomaly_detection')),
    detection_method VARCHAR(50) NOT NULL,
    intervention_details JSONB DEFAULT '{}',
    original_output JSONB DEFAULT '{}',
    corrected_output JSONB DEFAULT '{}',
    confidence_score_before DECIMAL(5,4),
    confidence_score_after DECIMAL(5,4),
    status VARCHAR(20) DEFAULT 'detected' CHECK (status IN ('detected', 'corrected', 'escalated', 'resolved')),
    detected_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMPTZ,
    resolved_by UUID REFERENCES users(user_id) ON DELETE SET NULL,
    order_id UUID REFERENCES orders(order_id) ON DELETE SET NULL,
    user_id UUID REFERENCES users(user_id) ON DELETE SET NULL
);

CREATE INDEX idx_ai_agent_interventions_agent ON ai_agent_interventions(agent_name, detected_at DESC);
CREATE INDEX idx_ai_agent_interventions_status ON ai_agent_interventions(status);

-- -----------------------------------------------------------------------------
-- 14. Notification log
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS notification_log (
    notification_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    channel VARCHAR(20) NOT NULL CHECK (channel IN ('push', 'sms', 'email', 'in_app')),
    notification_type VARCHAR(50) NOT NULL,
    title VARCHAR(255),
    body TEXT,
    payload JSONB DEFAULT '{}',
    is_read BOOLEAN DEFAULT false,
    sent_at TIMESTAMPTZ,
    delivered_at TIMESTAMPTZ,
    failed_at TIMESTAMPTZ,
    failure_reason TEXT,
    external_id VARCHAR(100),
    idempotency_key VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_notification_log_user_id ON notification_log(user_id, created_at DESC);
CREATE INDEX idx_notification_log_type ON notification_log(notification_type);
CREATE INDEX idx_notification_log_idempotency ON notification_log(idempotency_key);

-- -----------------------------------------------------------------------------
-- 15. Webhook events (idempotency)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS webhook_events (
    webhook_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    provider VARCHAR(50) NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}',
    signature VARCHAR(500),
    processed BOOLEAN DEFAULT false,
    processing_attempts INTEGER DEFAULT 0,
    last_processed_at TIMESTAMPTZ,
    error_message TEXT,
    idempotency_key VARCHAR(100) UNIQUE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_webhook_events_provider ON webhook_events(provider, created_at DESC);
CREATE INDEX idx_webhook_events_processed ON webhook_events(processed, processing_attempts);
CREATE INDEX idx_webhook_events_idempotency ON webhook_events(idempotency_key);

-- -----------------------------------------------------------------------------
-- 16. SOP sections
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sop_sections (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    sop_version TEXT NOT NULL,
    section_id TEXT NOT NULL,
    section_title TEXT NOT NULL,
    agent TEXT,
    workflow_category TEXT,
    procedure JSONB NOT NULL DEFAULT '[]',
    key_rules TEXT[],
    inputs TEXT[],
    outputs TEXT[],
    related_tables TEXT[],
    related_apis TEXT[],
    related_agents TEXT[],
    vector_embedding VECTOR(1536),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(sop_version, section_id)
);

CREATE INDEX idx_sop_sections_agent ON sop_sections(agent);
CREATE INDEX idx_sop_sections_search ON sop_sections USING gin(to_tsvector('english', section_title || ' ' || COALESCE(agent, '')));
