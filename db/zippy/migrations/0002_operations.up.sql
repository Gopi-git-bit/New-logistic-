BEGIN;

CREATE TYPE zippy.vehicle_status AS ENUM ('pending', 'approved', 'suspended', 'rejected', 'retired');
CREATE TYPE zippy.order_status AS ENUM ('pending', 'quoted', 'confirmed', 'assigned', 'in_transit', 'delivered', 'cancelled');
CREATE TYPE zippy.participant_role AS ENUM ('customer', 'vendor');
CREATE TYPE zippy.offer_status AS ENUM ('pending', 'accepted', 'declined', 'expired', 'cancelled');
CREATE TYPE zippy.trip_status AS ENUM ('planned', 'assigned', 'active', 'completed', 'cancelled', 'exception');
CREATE TYPE zippy.milestone_kind AS ENUM ('pickup', 'in_transit', 'arrival', 'delivery', 'pod_pending', 'exception');

CREATE TABLE zippy.vehicle_models (
    vehicle_model_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    platform_id uuid NOT NULL REFERENCES zippy.platforms(platform_id),
    model_code text NOT NULL,
    display_name text NOT NULL,
    capacity_kg numeric(12,3) NOT NULL CHECK (capacity_kg > 0),
    body_type text NOT NULL,
    source_version text NOT NULL,
    approved_by_account_id uuid NOT NULL,
    approved_at timestamptz NOT NULL,
    active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (platform_id, vehicle_model_id),
    UNIQUE (platform_id, model_code, source_version),
    FOREIGN KEY (platform_id, approved_by_account_id) REFERENCES zippy.accounts(platform_id, account_id)
);

CREATE TABLE zippy.vehicles (
    vehicle_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    platform_id uuid NOT NULL REFERENCES zippy.platforms(platform_id),
    vendor_profile_id uuid NOT NULL,
    vehicle_model_id uuid NOT NULL,
    registration_number text NOT NULL,
    status zippy.vehicle_status NOT NULL DEFAULT 'pending',
    approved_by_account_id uuid,
    approved_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (platform_id, vehicle_id),
    UNIQUE (platform_id, registration_number),
    FOREIGN KEY (platform_id, vendor_profile_id) REFERENCES zippy.vendor_profiles(platform_id, vendor_profile_id),
    FOREIGN KEY (platform_id, vehicle_model_id) REFERENCES zippy.vehicle_models(platform_id, vehicle_model_id),
    FOREIGN KEY (platform_id, approved_by_account_id) REFERENCES zippy.accounts(platform_id, account_id),
    CHECK ((status = 'approved' AND approved_by_account_id IS NOT NULL AND approved_at IS NOT NULL) OR status <> 'approved')
);

CREATE TABLE zippy.vehicle_documents (
    vehicle_document_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    platform_id uuid NOT NULL REFERENCES zippy.platforms(platform_id),
    vehicle_id uuid NOT NULL,
    document_type text NOT NULL,
    object_key text NOT NULL,
    checksum_sha256 text NOT NULL CHECK (checksum_sha256 ~ '^[0-9a-f]{64}$'),
    valid_from date,
    valid_until date,
    verification_status text NOT NULL DEFAULT 'pending' CHECK (verification_status IN ('pending', 'verified', 'rejected', 'expired')),
    verified_by_account_id uuid,
    verified_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (platform_id, vehicle_document_id),
    UNIQUE (platform_id, vehicle_id, document_type, object_key),
    FOREIGN KEY (platform_id, vehicle_id) REFERENCES zippy.vehicles(platform_id, vehicle_id),
    FOREIGN KEY (platform_id, verified_by_account_id) REFERENCES zippy.accounts(platform_id, account_id),
    CHECK (valid_until IS NULL OR valid_from IS NULL OR valid_until >= valid_from),
    CHECK ((verification_status = 'verified' AND verified_by_account_id IS NOT NULL AND verified_at IS NOT NULL) OR verification_status <> 'verified')
);

CREATE TABLE zippy.quotes (
    quote_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    platform_id uuid NOT NULL REFERENCES zippy.platforms(platform_id),
    customer_profile_id uuid NOT NULL,
    policy_version text NOT NULL,
    input_hash_sha256 text NOT NULL CHECK (input_hash_sha256 ~ '^[0-9a-f]{64}$'),
    input_evidence jsonb NOT NULL,
    amount numeric(18,2) NOT NULL CHECK (amount >= 0),
    currency_code varchar(3) NOT NULL CHECK (currency_code ~ '^[A-Z]{3}$'),
    expires_at timestamptz NOT NULL,
    created_by_account_id uuid NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (platform_id, quote_id),
    UNIQUE (platform_id, customer_profile_id, policy_version, input_hash_sha256),
    FOREIGN KEY (platform_id, customer_profile_id) REFERENCES zippy.customer_profiles(platform_id, customer_profile_id),
    FOREIGN KEY (platform_id, created_by_account_id) REFERENCES zippy.accounts(platform_id, account_id),
    CHECK (jsonb_typeof(input_evidence) = 'object'),
    CHECK (expires_at > created_at)
);

CREATE TABLE zippy.orders (
    order_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    platform_id uuid NOT NULL REFERENCES zippy.platforms(platform_id),
    booking_customer_profile_id uuid NOT NULL,
    quote_id uuid NOT NULL,
    status zippy.order_status NOT NULL DEFAULT 'pending',
    cargo_description text NOT NULL,
    cargo_weight_kg numeric(12,3) NOT NULL CHECK (cargo_weight_kg > 0),
    special_handling_code text,
    version integer NOT NULL DEFAULT 1 CHECK (version > 0),
    created_by_account_id uuid NOT NULL,
    correlation_id uuid NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (platform_id, order_id),
    FOREIGN KEY (platform_id, booking_customer_profile_id) REFERENCES zippy.customer_profiles(platform_id, customer_profile_id),
    FOREIGN KEY (platform_id, quote_id) REFERENCES zippy.quotes(platform_id, quote_id),
    FOREIGN KEY (platform_id, created_by_account_id) REFERENCES zippy.accounts(platform_id, account_id)
);

CREATE TABLE zippy.order_stops (
    order_stop_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    platform_id uuid NOT NULL REFERENCES zippy.platforms(platform_id),
    order_id uuid NOT NULL,
    stop_sequence smallint NOT NULL CHECK (stop_sequence > 0),
    stop_kind text NOT NULL CHECK (stop_kind IN ('pickup', 'delivery', 'waypoint')),
    address_text text NOT NULL,
    latitude numeric(9,6),
    longitude numeric(9,6),
    accuracy_meters numeric(10,2) CHECK (accuracy_meters IS NULL OR accuracy_meters >= 0),
    source text NOT NULL,
    created_by_account_id uuid NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (platform_id, order_id, stop_sequence),
    FOREIGN KEY (platform_id, order_id) REFERENCES zippy.orders(platform_id, order_id),
    FOREIGN KEY (platform_id, created_by_account_id) REFERENCES zippy.accounts(platform_id, account_id),
    CHECK (latitude IS NULL OR latitude BETWEEN -90 AND 90),
    CHECK (longitude IS NULL OR longitude BETWEEN -180 AND 180)
);

CREATE TABLE zippy.transaction_participants (
    transaction_participant_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    platform_id uuid NOT NULL REFERENCES zippy.platforms(platform_id),
    order_id uuid NOT NULL,
    participant_role zippy.participant_role NOT NULL,
    customer_profile_id uuid,
    vendor_profile_id uuid,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (platform_id, order_id, participant_role),
    FOREIGN KEY (platform_id, order_id) REFERENCES zippy.orders(platform_id, order_id),
    FOREIGN KEY (platform_id, customer_profile_id) REFERENCES zippy.customer_profiles(platform_id, customer_profile_id),
    FOREIGN KEY (platform_id, vendor_profile_id) REFERENCES zippy.vendor_profiles(platform_id, vendor_profile_id),
    CHECK (
        (participant_role = 'customer' AND customer_profile_id IS NOT NULL AND vendor_profile_id IS NULL) OR
        (participant_role = 'vendor' AND vendor_profile_id IS NOT NULL AND customer_profile_id IS NULL)
    )
);

CREATE TABLE zippy.dispatch_offers (
    dispatch_offer_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    platform_id uuid NOT NULL REFERENCES zippy.platforms(platform_id),
    order_id uuid NOT NULL,
    vendor_profile_id uuid NOT NULL,
    vehicle_id uuid,
    driver_profile_id uuid,
    status zippy.offer_status NOT NULL DEFAULT 'pending',
    scoring_input_version text NOT NULL,
    idempotency_key text NOT NULL,
    expires_at timestamptz NOT NULL,
    responded_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (platform_id, dispatch_offer_id),
    UNIQUE (platform_id, idempotency_key),
    FOREIGN KEY (platform_id, order_id) REFERENCES zippy.orders(platform_id, order_id),
    FOREIGN KEY (platform_id, vendor_profile_id) REFERENCES zippy.vendor_profiles(platform_id, vendor_profile_id),
    FOREIGN KEY (platform_id, vehicle_id) REFERENCES zippy.vehicles(platform_id, vehicle_id),
    FOREIGN KEY (platform_id, driver_profile_id) REFERENCES zippy.driver_profiles(platform_id, driver_profile_id),
    CHECK (expires_at > created_at),
    CHECK ((status IN ('accepted', 'declined') AND responded_at IS NOT NULL) OR status NOT IN ('accepted', 'declined'))
);

CREATE UNIQUE INDEX dispatch_one_accepted_offer_idx
    ON zippy.dispatch_offers (platform_id, order_id)
    WHERE status = 'accepted';

CREATE TABLE zippy.trips (
    trip_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    platform_id uuid NOT NULL REFERENCES zippy.platforms(platform_id),
    order_id uuid NOT NULL,
    status zippy.trip_status NOT NULL DEFAULT 'planned',
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (platform_id, trip_id),
    UNIQUE (platform_id, order_id),
    FOREIGN KEY (platform_id, order_id) REFERENCES zippy.orders(platform_id, order_id)
);

CREATE TABLE zippy.trip_assignments (
    trip_assignment_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    platform_id uuid NOT NULL REFERENCES zippy.platforms(platform_id),
    trip_id uuid NOT NULL,
    dispatch_offer_id uuid NOT NULL,
    vendor_profile_id uuid NOT NULL,
    vehicle_id uuid NOT NULL,
    driver_profile_id uuid NOT NULL,
    assigned_by_account_id uuid NOT NULL,
    assigned_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    released_at timestamptz,
    correlation_id uuid NOT NULL,
    UNIQUE (platform_id, trip_id, assigned_at),
    FOREIGN KEY (platform_id, trip_id) REFERENCES zippy.trips(platform_id, trip_id),
    FOREIGN KEY (platform_id, dispatch_offer_id) REFERENCES zippy.dispatch_offers(platform_id, dispatch_offer_id),
    FOREIGN KEY (platform_id, vendor_profile_id) REFERENCES zippy.vendor_profiles(platform_id, vendor_profile_id),
    FOREIGN KEY (platform_id, vehicle_id) REFERENCES zippy.vehicles(platform_id, vehicle_id),
    FOREIGN KEY (platform_id, driver_profile_id) REFERENCES zippy.driver_profiles(platform_id, driver_profile_id),
    FOREIGN KEY (platform_id, assigned_by_account_id) REFERENCES zippy.accounts(platform_id, account_id),
    CHECK (released_at IS NULL OR released_at >= assigned_at)
);

CREATE UNIQUE INDEX trip_active_vehicle_idx
    ON zippy.trip_assignments (platform_id, vehicle_id)
    WHERE released_at IS NULL;
CREATE UNIQUE INDEX trip_active_driver_idx
    ON zippy.trip_assignments (platform_id, driver_profile_id)
    WHERE released_at IS NULL;

CREATE TABLE zippy.trip_milestones (
    trip_milestone_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    platform_id uuid NOT NULL REFERENCES zippy.platforms(platform_id),
    trip_id uuid NOT NULL,
    milestone zippy.milestone_kind NOT NULL,
    sequence_no integer NOT NULL CHECK (sequence_no > 0),
    actor_account_id uuid NOT NULL,
    source text NOT NULL CHECK (source IN ('manual', 'system', 'verified_webhook')),
    reason text,
    correlation_id uuid NOT NULL,
    occurred_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (platform_id, trip_id, sequence_no),
    FOREIGN KEY (platform_id, trip_id) REFERENCES zippy.trips(platform_id, trip_id),
    FOREIGN KEY (platform_id, actor_account_id) REFERENCES zippy.accounts(platform_id, account_id)
);

CREATE TABLE zippy.trip_location_history (
    location_sample_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    platform_id uuid NOT NULL REFERENCES zippy.platforms(platform_id),
    trip_id uuid NOT NULL,
    vehicle_id uuid NOT NULL,
    actor_account_id uuid NOT NULL,
    latitude numeric(9,6) NOT NULL CHECK (latitude BETWEEN -90 AND 90),
    longitude numeric(9,6) NOT NULL CHECK (longitude BETWEEN -180 AND 180),
    accuracy_meters numeric(10,2) NOT NULL CHECK (accuracy_meters >= 0),
    source text NOT NULL CHECK (source IN ('browser', 'manual', 'device')),
    consent_reference text NOT NULL,
    correlation_id uuid NOT NULL,
    captured_at timestamptz NOT NULL,
    received_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    FOREIGN KEY (platform_id, trip_id) REFERENCES zippy.trips(platform_id, trip_id),
    FOREIGN KEY (platform_id, vehicle_id) REFERENCES zippy.vehicles(platform_id, vehicle_id),
    FOREIGN KEY (platform_id, actor_account_id) REFERENCES zippy.accounts(platform_id, account_id)
);

CREATE TABLE zippy.pod_documents (
    pod_document_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    platform_id uuid NOT NULL REFERENCES zippy.platforms(platform_id),
    order_id uuid NOT NULL,
    trip_id uuid NOT NULL,
    uploaded_by_account_id uuid NOT NULL,
    object_key text NOT NULL,
    content_type text NOT NULL,
    byte_size bigint NOT NULL CHECK (byte_size > 0),
    checksum_sha256 text NOT NULL CHECK (checksum_sha256 ~ '^[0-9a-f]{64}$'),
    verification_status text NOT NULL DEFAULT 'pending' CHECK (verification_status IN ('pending', 'accepted', 'rejected', 'manual_review')),
    verified_by_account_id uuid,
    verified_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (platform_id, pod_document_id),
    UNIQUE (platform_id, object_key),
    FOREIGN KEY (platform_id, order_id) REFERENCES zippy.orders(platform_id, order_id),
    FOREIGN KEY (platform_id, trip_id) REFERENCES zippy.trips(platform_id, trip_id),
    FOREIGN KEY (platform_id, uploaded_by_account_id) REFERENCES zippy.accounts(platform_id, account_id),
    FOREIGN KEY (platform_id, verified_by_account_id) REFERENCES zippy.accounts(platform_id, account_id),
    CHECK ((verification_status IN ('accepted', 'rejected') AND verified_by_account_id IS NOT NULL AND verified_at IS NOT NULL) OR verification_status NOT IN ('accepted', 'rejected'))
);

CREATE INDEX vehicles_owner_status_idx ON zippy.vehicles (platform_id, vendor_profile_id, status);
CREATE INDEX orders_customer_status_idx ON zippy.orders (platform_id, booking_customer_profile_id, status, created_at DESC);
CREATE INDEX offers_order_status_idx ON zippy.dispatch_offers (platform_id, order_id, status, expires_at);
CREATE INDEX trips_status_idx ON zippy.trips (platform_id, status, updated_at DESC);
CREATE INDEX milestones_trip_time_idx ON zippy.trip_milestones (platform_id, trip_id, occurred_at);
CREATE INDEX locations_trip_time_idx ON zippy.trip_location_history (platform_id, trip_id, captured_at DESC);
CREATE INDEX pod_order_status_idx ON zippy.pod_documents (platform_id, order_id, verification_status);

COMMIT;