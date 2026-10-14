-- M1: Seed data for local development and E2E tests

-- -----------------------------------------------------------------------------
-- Users
-- -----------------------------------------------------------------------------
INSERT INTO public.users (user_id, email, phone_number, password_hash, first_name, last_name, base_role, active_role, email_verified, phone_verified)
VALUES
    ('00000000-0000-0000-0000-000000000001', 'admin@zippy.local', '9999999999', 'hashed_admin_pass', 'System', 'Admin', 'admin', NULL, true, true),
    ('00000000-0000-0000-0000-000000000002', 'customer@acme.local', '8888888888', 'hashed_customer_pass', 'Ravi', 'Sharma', 'customer', NULL, true, true),
    ('00000000-0000-0000-0000-000000000003', 'driver@zippy.local', '7777777777', 'hashed_driver_pass', 'Mohit', 'Kumar', 'driver', NULL, true, true),
    ('00000000-0000-0000-0000-000000000004', 'fleet@speedways.local', '6666666666', 'hashed_company_pass', 'Asha', 'Patel', 'transport_company', 'provider', true, true)
ON CONFLICT (user_id) DO NOTHING;

-- -----------------------------------------------------------------------------
-- Customer profile
-- -----------------------------------------------------------------------------
INSERT INTO public.customer_profiles (customer_id, user_id, company_name, customer_category, gst_pan_number, company_phone, company_email, verification_status)
VALUES
    ('10000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000002', 'Acme Warehousing Pvt Ltd', 'Warehouse', '27AABCU9603R1ZX', '8888888888', 'billing@acme.local', 'verified')
ON CONFLICT DO NOTHING;

-- -----------------------------------------------------------------------------
-- Driver profile
-- -----------------------------------------------------------------------------
INSERT INTO public.driver_profiles (driver_id, user_id, date_of_birth, years_of_experience, driver_status, license_number, license_verified)
VALUES
    ('20000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000003', '1988-04-15', 8, 'Vehicle Owner', 'MH02-2020-1234567', true)
ON CONFLICT DO NOTHING;

-- -----------------------------------------------------------------------------
-- Transport company
-- -----------------------------------------------------------------------------
INSERT INTO public.transport_companies (transport_company_id, user_id, company_name, gst_number, pan_number, service_areas, specializations, is_verified)
VALUES
    ('30000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000004', 'Speedways Logistics', '27AAICS1234A1Z5', 'AAICS1234A', ARRAY['Mumbai', 'Pune', 'Nashik'], ARRAY['Full Truckload', 'Part Truckload'], true)
ON CONFLICT DO NOTHING;

-- -----------------------------------------------------------------------------
-- Vehicle models
-- -----------------------------------------------------------------------------
INSERT INTO public.vehicle_models (model_id, brand, model, vehicle_type, body_type, capacity_tons, length_ft, width_ft, height_ft)
VALUES
    ('40000000-0000-0000-0000-000000000001', 'Tata', '407', 'LCV', 'Open Body', 2.50, 14.0, 6.0, 6.0),
    ('40000000-0000-0000-0000-000000000002', 'Ashok Leyland', 'Dost+', 'LCV', 'Closed Body', 1.50, 10.0, 5.0, 5.0),
    ('40000000-0000-0000-0000-000000000003', 'Tata', 'LPT 1613', 'MCV', 'Open Body', 9.00, 22.0, 7.5, 7.0),
    ('40000000-0000-0000-0000-000000000004', 'Mahindra', 'Blazo X 49', 'HCV', 'Open Body', 25.00, 32.0, 8.5, 8.0)
ON CONFLICT DO NOTHING;

-- -----------------------------------------------------------------------------
-- Vehicles
-- -----------------------------------------------------------------------------
INSERT INTO public.vehicles (vehicle_id, owner_id, model_id, assigned_driver_id, registration_number, vehicle_type, body_type, capacity_tons, current_status, ownership_type)
VALUES
    ('50000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000003', '40000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000001', 'MH-01-AB-1234', 'LCV', 'Open Body', 2.50, 'online', 'personal'),
    ('50000000-0000-0000-0000-000000000002', '00000000-0000-0000-0000-000000000004', '40000000-0000-0000-0000-000000000003', NULL, 'MH-12-XY-5678', 'MCV', 'Open Body', 9.00, 'offline', 'company')
ON CONFLICT DO NOTHING;

-- -----------------------------------------------------------------------------
-- SOP sections (machine-readable knowledge)
-- -----------------------------------------------------------------------------
INSERT INTO public.sop_sections (
    sop_version, section_id, section_title, agent, workflow_category,
    procedure, key_rules, inputs, outputs, related_tables, related_apis, related_agents
) VALUES
(
    '1.0.0',
    '1.1',
    'User Onboarding',
    'Platform Administration',
    'User Management Workflow',
    jsonb_build_array(
        'New users register through respective applications.',
        'AI Verification Agent processes registration documents using OCR.',
        'System creates user record with appropriate base_role.',
        'Email and phone verification completed.',
        'Admin approval required for transport company registrations.'
    ),
    ARRAY['All users must verify phone number.', 'Transport companies require admin approval.'],
    ARRAY['registration_payload', 'documents'],
    ARRAY['user_id', 'verification_status'],
    ARRAY['users', 'customer_profiles', 'driver_profiles', 'transport_companies'],
    ARRAY['OCR API'],
    ARRAY['Verification Agent', 'Platform Administration Agent']
),
(
    '1.0.0',
    '2.1',
    'Order Creation',
    'OMS',
    'Order Lifecycle Workflow',
    jsonb_build_array(
        'Customers submit transportation requests via mobile or web.',
        'OMS AI Agent validates order details: geocoding, cargo specs, timeframe.',
        'System assigns unique order_id and timestamps request.',
        'Order stored in orders table with status pending.',
        'Customer receives automated confirmation via WebSocket.'
    ),
    ARRAY['All orders must have valid pickup and delivery locations.', 'Cargo details are mandatory.', 'No pricing before validation.'],
    ARRAY['customer_request_payload', 'cargo_data', 'pickup_location', 'delivery_location'],
    ARRAY['order_id', 'order_status', 'customer_notification'],
    ARRAY['orders', 'users'],
    ARRAY['Mapbox Geocoding API'],
    ARRAY['OMS Agent', 'Verification Agent']
),
(
    '1.0.0',
    '3.1',
    'Provider Assignment',
    'TMS',
    'Order Lifecycle Workflow',
    jsonb_build_array(
        'TMS identifies available providers based on order requirements.',
        'System sets provider_type and provider_id.',
        'Commission structure applied based on provider_type.',
        'Provider receives notification with order details.',
        'Provider accepts or declines order.'
    ),
    ARRAY['Driver providers pay 10% commission.', 'Transport companies pay flat INR 700 service fee.'],
    ARRAY['order_id', 'provider_candidates'],
    ARRAY['assigned_provider_id', 'commission_amount', 'service_fee'],
    ARRAY['orders', 'driver_profiles', 'transport_companies'],
    ARRAY['Notification API'],
    ARRAY['TMS Agent', 'Resource Management Agent']
),
(
    '1.0.0',
    '5.1',
    'Payment Initiation',
    'Payment & Settlement',
    'Payment Workflow',
    jsonb_build_array(
        'Payment agent initiates payment based on order status.',
        'System uses Razorpay primary / Stripe failover.',
        'Payment details recorded in payments table.',
        'Transactions logged in payment_transactions.',
        'Customer receives payment confirmation.'
    ),
    ARRAY['Payment modes: full, partial (min 50%), to_pay.', 'Customers do not pay commission.'],
    ARRAY['order_id', 'amount', 'payment_mode'],
    ARRAY['payment_id', 'transaction_ids'],
    ARRAY['orders', 'payments', 'payment_transactions'],
    ARRAY['Razorpay API', 'Stripe API'],
    ARRAY['Payment & Settlement Agent']
)
ON CONFLICT (sop_version, section_id) DO NOTHING;
