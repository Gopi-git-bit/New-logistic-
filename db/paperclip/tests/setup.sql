SET ROLE paperclip_migrator;
SELECT set_config('paperclip.tenant_id','11111111-1111-1111-1111-111111111111',false);
INSERT INTO paperclip.tenants(id,name) VALUES ('11111111-1111-1111-1111-111111111111','one');
INSERT INTO paperclip.agents(id,tenant_id,agent_key) VALUES ('11111111-1111-1111-1111-111111111112','11111111-1111-1111-1111-111111111111','agent-one');
INSERT INTO paperclip.policy_versions(id,tenant_id,policy_key,version,policy_document,checksum_sha256,is_active) VALUES ('11111111-1111-1111-1111-111111111113','11111111-1111-1111-1111-111111111111','governance','v1','{"approval":"required"}',encode(public.digest('{"approval":"required"}'::jsonb::text,'sha256'),'hex'),true);
-- Zero-budget agent: any positive cost must be denied and no grant may be issued to it.
INSERT INTO paperclip.agents(id,tenant_id,agent_key,monthly_budget_usd) VALUES ('11111111-1111-1111-1111-111111111114','11111111-1111-1111-1111-111111111111','agent-zero',0);
-- Inactive policy: proposals bound to it must fail closed at grant issuance.
INSERT INTO paperclip.policy_versions(id,tenant_id,policy_key,version,policy_document,checksum_sha256,is_active) VALUES ('11111111-1111-1111-1111-111111111115','11111111-1111-1111-1111-111111111111','governance','v2-inactive','{"approval":"required"}',encode(public.digest('{"approval":"required"}'::jsonb::text,'sha256'),'hex'),false);
-- Inactive agent: must receive no grant even with approval.
INSERT INTO paperclip.agents(id,tenant_id,agent_key,is_active) VALUES ('11111111-1111-1111-1111-111111111116','11111111-1111-1111-1111-111111111111','agent-inactive',false);
-- Budgeted agent: partial spend is recorded, a cost exceeding the remainder is denied.
INSERT INTO paperclip.agents(id,tenant_id,agent_key,monthly_budget_usd) VALUES ('11111111-1111-1111-1111-111111111118','11111111-1111-1111-1111-111111111111','agent-budgeted',1.00);
INSERT INTO paperclip.governance_tasks(id,tenant_id,task_key) VALUES ('11111111-1111-1111-1111-111111111119','11111111-1111-1111-1111-111111111111','task-one');
-- Mutable policy: its document is altered after proposal creation to prove issue-time checksum re-verification.
INSERT INTO paperclip.policy_versions(id,tenant_id,policy_key,version,policy_document,checksum_sha256,is_active) VALUES ('11111111-1111-1111-1111-11111111111a','11111111-1111-1111-1111-111111111111','mutable','v1','{"approval":"required"}',encode(public.digest('{"approval":"required"}'::jsonb::text,'sha256'),'hex'),true);
SELECT set_config('paperclip.tenant_id','22222222-2222-2222-2222-222222222222',false);
INSERT INTO paperclip.tenants(id,name) VALUES ('22222222-2222-2222-2222-222222222222','two');
INSERT INTO paperclip.governance_tasks(id,tenant_id,task_key) VALUES ('22222222-2222-2222-2222-222222222229','22222222-2222-2222-2222-222222222222','task-two');
INSERT INTO paperclip.agents(id,tenant_id,agent_key) VALUES ('22222222-2222-2222-2222-222222222223','22222222-2222-2222-2222-222222222222','agent-two');
INSERT INTO paperclip.policy_versions(id,tenant_id,policy_key,version,policy_document,checksum_sha256,is_active) VALUES ('22222222-2222-2222-2222-222222222224','22222222-2222-2222-2222-222222222222','governance','v1','{"approval":"required"}',encode(public.digest('{"approval":"required"}'::jsonb::text,'sha256'),'hex'),true);
SELECT set_config('paperclip.tenant_id','',false);
RESET ROLE;