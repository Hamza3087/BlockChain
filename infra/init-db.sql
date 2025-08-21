-- Initialize the ReplantWorld database
-- This script runs when the PostgreSQL container starts for the first time

-- Create extensions that might be useful
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Create a schema for application data (optional, but good practice)
-- CREATE SCHEMA IF NOT EXISTS replantworld;

-- Set default search path
-- SET search_path TO replantworld, public;

-- Log initialization
DO $$
BEGIN
    RAISE NOTICE 'ReplantWorld database initialized successfully';
END $$;
