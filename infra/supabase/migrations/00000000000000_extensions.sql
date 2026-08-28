-- M1: Enable required PostgreSQL extensions
-- Run before any other migration.

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "postgis";
-- pgvector's extension name is `vector` (both here and on Supabase)
CREATE EXTENSION IF NOT EXISTS "vector";

-- Confirm
SELECT extname, extversion FROM pg_extension WHERE extname IN ('uuid-ossp', 'pgcrypto', 'postgis', 'vector');
