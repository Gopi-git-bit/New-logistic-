SELECT set_config('zippy.platform_id', '10000000-0000-0000-0000-000000000001', false);
SELECT set_config('zippy.account_id', 'a0000000-0000-0000-0000-000000000001', false);
SELECT count(*)
  FROM zippy.claim_durable_tasks(
      '10000000-0000-0000-0000-000000000001',
      'synthetic_concurrent',
      'concurrent-worker-' || :client_id,
      60,
      1
  );