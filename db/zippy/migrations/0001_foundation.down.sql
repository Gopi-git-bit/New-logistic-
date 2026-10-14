BEGIN;

DROP TABLE IF EXISTS zippy.admin_account_actions;
DROP TABLE IF EXISTS zippy.driver_associations;
DROP TABLE IF EXISTS zippy.driver_profiles;
DROP TABLE IF EXISTS zippy.company_memberships;
DROP TABLE IF EXISTS zippy.vendor_profiles;
DROP TABLE IF EXISTS zippy.customer_profiles;
DROP TABLE IF EXISTS zippy.legal_entities;
DROP TABLE IF EXISTS zippy.account_role_memberships;
DROP TABLE IF EXISTS zippy.roles;
DROP TABLE IF EXISTS zippy.accounts;
DROP TABLE IF EXISTS zippy.platforms;
DROP TABLE IF EXISTS zippy.schema_migrations;

DROP TYPE IF EXISTS zippy.admin_action_kind;
DROP TYPE IF EXISTS zippy.party_kind;
DROP TYPE IF EXISTS zippy.account_status;

ALTER DEFAULT PRIVILEGES IN SCHEMA zippy GRANT EXECUTE ON FUNCTIONS TO PUBLIC;
DROP SCHEMA IF EXISTS zippy;
DROP EXTENSION IF EXISTS pgcrypto;

COMMIT;