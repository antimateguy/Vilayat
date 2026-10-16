-- Runs once on first start of an empty data volume.
-- The Alembic migrations also create these extensions (IF NOT EXISTS), because a
-- managed production database never runs this file.
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS vector;
