-- PostgreSQL initialization script for SAO application

-- Create database (already created by POSTGRES_DB)
-- CREATE DATABASE sao_db;

-- Create user (already created by POSTGRES_USER)
-- CREATE USER saodbuser WITH PASSWORD 'saodbuser';

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE sao_db TO saodbuser;

-- Connect to the application database
\c sao_db

-- Grant schema privileges
GRANT ALL ON SCHEMA public TO saodbuser;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO saodbuser;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO saodbuser;

-- Create any initial tables or data here
-- Example:
-- CREATE TABLE IF NOT EXISTS test_table (
--     id SERIAL PRIMARY KEY,
--     name VARCHAR(100) NOT NULL,
--     created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
-- );

-- Insert initial data if needed
-- INSERT INTO test_table (name) VALUES ('Initial data');

-- Display confirmation
SELECT 'PostgreSQL initialization completed successfully' AS status;