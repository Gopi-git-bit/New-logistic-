BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE SCHEMA zippy;

CREATE TABLE zippy.schema_migrations (
    version text PRIMARY KEY,
    checksum_sha256 text NOT NULL CHECK (checksum_sha256 ~ '^[0-9a-f]{64}$'),
    applied_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

ALTER DEFAULT PRIVILEGES IN SCHEMA zippy REVOKE ALL ON TABLES FROM PUBLIC;
ALTER DEFAULT PRIVILEGES IN SCHEMA zippy REVOKE ALL ON SEQUENCES FROM PUBLIC;
ALTER DEFAULT PRIVILEGES IN SCHEMA zippy REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;

CREATE TYPE zippy.account_status AS ENUM ('pending', 'active', 'suspended', 'blocked');
CREATE TYPE zippy.party_kind AS ENUM ('customer', 'vendor', 'transport_company');
CREATE TYPE zippy.admin_action_kind AS ENUM ('create', 'block', 'suspend', 'unblock');

CREATE TABLE zippy.platforms (
    platform_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    platform_key text NOT NULL UNIQUE,
    display_name text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CHECK (platform_key ~ '^[a-z][a-z0-9_]{2,62}$')
);

CREATE TABLE zippy.accounts (
    account_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    platform_id uuid NOT NULL REFERENCES zippy.platforms(platform_id),
    external_subject text NOT NULL,
    email_normalized text,
    phone_e164 text,
    status zippy.account_status NOT NULL DEFAULT 'pending',
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (platform_id, account_id),
    UNIQUE (platform_id, external_subject),
    UNIQUE (platform_id, email_normalized),
    UNIQUE (platform_id, phone_e164),
    CHECK (email_normalized IS NOT NULL OR phone_e164 IS NOT NULL)
);

CREATE TABLE zippy.roles (
    role_code text PRIMARY KEY,
    description text NOT NULL
);

INSERT INTO zippy.roles (role_code, description) VALUES
    ('customer', 'May act as a booking party when authorized'),
    ('vendor', 'May provide vehicle capacity when eligible'),
    ('driver', 'May operate an assigned vehicle when eligible'),
    ('transport_company', 'May participate through a legal entity'),
    ('admin', 'May perform explicitly authorized administration');

CREATE TABLE zippy.account_role_memberships (
    membership_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    platform_id uuid NOT NULL REFERENCES zippy.platforms(platform_id),
    account_id uuid NOT NULL,
    role_code text NOT NULL REFERENCES zippy.roles(role_code),
    valid_from timestamptz NOT NULL DEFAULT clock_timestamp(),
    valid_until timestamptz,
    granted_by_account_id uuid,
    correlation_id uuid NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (platform_id, account_id, role_code, valid_from),
    CHECK (valid_until IS NULL OR valid_until > valid_from),
    FOREIGN KEY (platform_id, account_id) REFERENCES zippy.accounts(platform_id, account_id),
    FOREIGN KEY (platform_id, granted_by_account_id) REFERENCES zippy.accounts(platform_id, account_id)
);

CREATE TABLE zippy.legal_entities (
    legal_entity_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    platform_id uuid NOT NULL REFERENCES zippy.platforms(platform_id),
    legal_name text NOT NULL,
    registration_reference text,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (platform_id, legal_entity_id),
    UNIQUE (platform_id, registration_reference)
);

CREATE TABLE zippy.customer_profiles (
    customer_profile_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    platform_id uuid NOT NULL REFERENCES zippy.platforms(platform_id),
    account_id uuid NOT NULL,
    legal_entity_id uuid,
    verification_status text NOT NULL DEFAULT 'pending' CHECK (verification_status IN ('pending', 'verified', 'rejected')),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (platform_id, customer_profile_id),
    UNIQUE (platform_id, account_id),
    FOREIGN KEY (platform_id, account_id) REFERENCES zippy.accounts(platform_id, account_id),
    FOREIGN KEY (platform_id, legal_entity_id) REFERENCES zippy.legal_entities(platform_id, legal_entity_id)
);

CREATE TABLE zippy.vendor_profiles (
    vendor_profile_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    platform_id uuid NOT NULL REFERENCES zippy.platforms(platform_id),
    account_id uuid,
    legal_entity_id uuid,
    eligibility_status text NOT NULL DEFAULT 'pending' CHECK (eligibility_status IN ('pending', 'approved', 'suspended', 'rejected')),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CHECK ((account_id IS NOT NULL)::integer + (legal_entity_id IS NOT NULL)::integer = 1),
    UNIQUE (platform_id, vendor_profile_id),
    UNIQUE (platform_id, account_id),
    UNIQUE (platform_id, legal_entity_id),
    FOREIGN KEY (platform_id, account_id) REFERENCES zippy.accounts(platform_id, account_id),
    FOREIGN KEY (platform_id, legal_entity_id) REFERENCES zippy.legal_entities(platform_id, legal_entity_id)
);

CREATE TABLE zippy.company_memberships (
    company_membership_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    platform_id uuid NOT NULL REFERENCES zippy.platforms(platform_id),
    legal_entity_id uuid NOT NULL,
    account_id uuid NOT NULL,
    membership_role text NOT NULL CHECK (membership_role IN ('owner', 'manager', 'dispatcher', 'driver')),
    valid_from timestamptz NOT NULL DEFAULT clock_timestamp(),
    valid_until timestamptz,
    UNIQUE (platform_id, legal_entity_id, account_id, membership_role, valid_from),
    CHECK (valid_until IS NULL OR valid_until > valid_from),
    FOREIGN KEY (platform_id, legal_entity_id) REFERENCES zippy.legal_entities(platform_id, legal_entity_id),
    FOREIGN KEY (platform_id, account_id) REFERENCES zippy.accounts(platform_id, account_id)
);

CREATE TABLE zippy.driver_profiles (
    driver_profile_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    platform_id uuid NOT NULL REFERENCES zippy.platforms(platform_id),
    account_id uuid NOT NULL,
    licence_reference text NOT NULL,
    eligibility_status text NOT NULL DEFAULT 'pending' CHECK (eligibility_status IN ('pending', 'approved', 'suspended', 'expired', 'rejected')),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (platform_id, driver_profile_id),
    UNIQUE (platform_id, account_id),
    UNIQUE (platform_id, licence_reference),
    FOREIGN KEY (platform_id, account_id) REFERENCES zippy.accounts(platform_id, account_id)
);

CREATE TABLE zippy.driver_associations (
    driver_association_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    platform_id uuid NOT NULL REFERENCES zippy.platforms(platform_id),
    driver_profile_id uuid NOT NULL,
    vendor_profile_id uuid NOT NULL,
    valid_from timestamptz NOT NULL,
    valid_until timestamptz,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (platform_id, driver_profile_id, vendor_profile_id, valid_from),
    CHECK (valid_until IS NULL OR valid_until > valid_from),
    FOREIGN KEY (platform_id, driver_profile_id) REFERENCES zippy.driver_profiles(platform_id, driver_profile_id),
    FOREIGN KEY (platform_id, vendor_profile_id) REFERENCES zippy.vendor_profiles(platform_id, vendor_profile_id)
);

CREATE TABLE zippy.admin_account_actions (
    admin_action_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    platform_id uuid NOT NULL REFERENCES zippy.platforms(platform_id),
    affected_account_id uuid NOT NULL,
    acting_admin_account_id uuid NOT NULL,
    action zippy.admin_action_kind NOT NULL,
    previous_status zippy.account_status,
    new_status zippy.account_status NOT NULL,
    reason_code text NOT NULL,
    reason_note text,
    correlation_id uuid NOT NULL,
    occurred_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CHECK (affected_account_id <> acting_admin_account_id),
    CHECK (
        (action = 'create' AND previous_status IS NULL) OR
        (action <> 'create' AND previous_status IS NOT NULL)
    ),
    FOREIGN KEY (platform_id, affected_account_id) REFERENCES zippy.accounts(platform_id, account_id),
    FOREIGN KEY (platform_id, acting_admin_account_id) REFERENCES zippy.accounts(platform_id, account_id)
);

CREATE INDEX accounts_platform_status_idx ON zippy.accounts (platform_id, status);
CREATE INDEX memberships_account_active_idx ON zippy.account_role_memberships (platform_id, account_id, valid_until);
CREATE INDEX company_memberships_account_idx ON zippy.company_memberships (platform_id, account_id, valid_until);
CREATE INDEX driver_associations_vendor_idx ON zippy.driver_associations (platform_id, vendor_profile_id, valid_until);
CREATE INDEX admin_actions_account_time_idx ON zippy.admin_account_actions (platform_id, affected_account_id, occurred_at DESC);

REVOKE ALL ON SCHEMA zippy FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA zippy FROM PUBLIC;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA zippy FROM PUBLIC;
REVOKE EXECUTE ON ALL FUNCTIONS IN SCHEMA zippy FROM PUBLIC;
GRANT USAGE ON SCHEMA zippy TO zippy_migrator;
GRANT USAGE ON SCHEMA zippy TO zippy_app, zippy_readonly;

COMMIT;