-- ==========================================
-- PostgreSQL Initialization Script
-- ==========================================
-- This script runs automatically when the PostgreSQL
-- container is first created.
-- It enables required extensions for TradeMeUp.
-- ==========================================

-- Enable UUID generation functions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Enable pgvector for embedding similarity search
CREATE EXTENSION IF NOT EXISTS "vector";

-- Log successful initialization
DO $$
BEGIN
    RAISE NOTICE 'PostgreSQL extensions initialized successfully';
    RAISE NOTICE 'Extensions available: uuid-ossp, vector';
END
$$;
