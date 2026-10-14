\set ON_ERROR_STOP on

SELECT CASE
    WHEN current_user = 'zippy_m2_runner'
     AND (SELECT rolsuper FROM pg_roles WHERE rolname = current_user)
    THEN true
    ELSE false
END AS disposable_superuser_fixture_setup \gset
\if :disposable_superuser_fixture_setup
\else
    \quit 1
\endif

INSERT INTO zippy.platforms (platform_id, platform_key, display_name) VALUES
    ('10000000-0000-0000-0000-000000000001', 'm2_primary', 'M2 Synthetic Primary'),
    ('20000000-0000-0000-0000-000000000002', 'm2_other', 'M2 Synthetic Other');

SELECT 'Synthetic platform fixtures created' AS result;