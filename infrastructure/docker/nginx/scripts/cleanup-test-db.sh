#!/bin/bash
# Test database cleanup script

set -e

echo "Starting test database cleanup..."

# Drop all tables
PGPASSWORD=$PGPASSWORD psql -h $PGHOST -p $PGPORT -U $PGUSER -d $PGDATABASE <<EOF
-- Disable foreign key checks
SET session_replication_role = 'replica';

-- Drop all tables
DO \$\$ DECLARE
    r RECORD;
BEGIN
    FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = 'public') LOOP
        EXECUTE 'DROP TABLE IF EXISTS ' || quote_ident(r.tablename) || ' CASCADE';
    END LOOP;
END \$\$;

-- Drop all types
DO \$\$ DECLARE
    r RECORD;
BEGIN
    FOR r IN (SELECT typname FROM pg_type WHERE typnamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public')) LOOP
        EXECUTE 'DROP TYPE IF EXISTS ' || quote_ident(r.typname) || ' CASCADE';
    END LOOP;
END \$\$;

-- Drop all sequences
DO \$\$ DECLARE
    r RECORD;
BEGIN
    FOR r IN (SELECT sequencename FROM pg_sequences WHERE schemaname = 'public') LOOP
        EXECUTE 'DROP SEQUENCE IF EXISTS ' || quote_ident(r.sequencename) || ' CASCADE';
    END LOOP;
END \$\$;

-- Drop all functions
DO \$\$ DECLARE
    r RECORD;
BEGIN
    FOR r IN (SELECT proname, oidvectortypes(proargtypes) AS args 
              FROM pg_proc 
              WHERE pronamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public')) LOOP
        EXECUTE 'DROP FUNCTION IF EXISTS ' || quote_ident(r.proname) || '(' || r.args || ') CASCADE';
    END LOOP;
END \$\$;

-- Re-enable foreign key checks
SET session_replication_role = 'origin';

-- Reset sequences (if any remain)
DO \$\$ DECLARE
    r RECORD;
BEGIN
    FOR r IN (SELECT sequencename FROM pg_sequences WHERE schemaname = 'public') LOOP
        EXECUTE 'ALTER SEQUENCE ' || quote_ident(r.sequencename) || ' RESTART WITH 1';
    END LOOP;
END \$\$;
EOF

echo "Test database cleaned successfully."