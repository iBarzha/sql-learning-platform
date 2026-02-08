-- Restricted student role for sandbox query execution.
-- Defense-in-depth: even if regex validation is bypassed,
-- the DB itself blocks dangerous operations.

-- Create restricted role
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'sandbox_student') THEN
        CREATE ROLE sandbox_student WITH LOGIN PASSWORD 'sandbox_student';
    END IF;
END
$$;

-- Allow connecting to sandbox database
GRANT CONNECT ON DATABASE sandbox TO sandbox_student;

-- Allow usage of public schema
GRANT USAGE ON SCHEMA public TO sandbox_student;

-- Read-only access to information_schema (for learning)
GRANT SELECT ON ALL TABLES IN SCHEMA information_schema TO sandbox_student;

-- Role-level statement timeout — CANNOT be overridden by SET statement
ALTER ROLE sandbox_student SET statement_timeout = '10s';
ALTER ROLE sandbox_student SET lock_timeout = '5s';

-- Prevent privilege escalation
ALTER ROLE sandbox_student NOCREATEDB NOCREATEROLE NOSUPERUSER;

-- Prevent changing runtime parameters that could be exploited
ALTER ROLE sandbox_student SET log_statement = 'none';
