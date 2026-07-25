-- AEON OS — Postgres Initialization
-- ===================================
-- Runs once when the postgres volume is first created.
-- The AEON application handles schema migrations via SQLAlchemy;
-- this file only ensures the database encoding and extensions are correct.

-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Enable pg_trgm for text search (used by RAG/knowledge base)
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Enable hstore for flexible metadata storage
CREATE EXTENSION IF NOT EXISTS "hstore";

-- Verify database is UTF8
DO $$
BEGIN
    IF current_setting('server_encoding') <> 'UTF8' THEN
        RAISE WARNING 'Server encoding is not UTF8: %', current_setting('server_encoding');
    END IF;
END;
$$;
