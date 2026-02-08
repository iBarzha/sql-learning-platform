-- Restricted student user for sandbox query execution.
-- Defense-in-depth: DB-level restrictions as safety net.

-- Create restricted user (if not exists)
CREATE USER IF NOT EXISTS 'sandbox_student'@'%' IDENTIFIED BY 'sandbox_student';

-- Global settings for safety
SET GLOBAL max_statement_time = 10;
SET GLOBAL max_join_size = 1000000;
SET GLOBAL sql_mode = 'STRICT_TRANS_TABLES,NO_ENGINE_SUBSTITUTION,ONLY_FULL_GROUP_BY';

-- Note: Per-database GRANTs are done dynamically in session_manager.py
-- when a session database is created, because each session uses
-- a unique database name (e.g., s_abc123).
