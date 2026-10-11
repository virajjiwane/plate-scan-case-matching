#!/bin/sh
# Runs once, on first initialisation of the data volume.
#
# Two roles, so the app can never bypass row-level security:
#   DB_OWNER_USER  owns the database and schema; runs migrations (DDL).
#   DB_APP_USER    used by the running app; DML only, not owner, NOBYPASSRLS.
set -eu

psql -v ON_ERROR_STOP=1 \
     --username "$POSTGRES_USER" \
     --dbname "$POSTGRES_DB" \
     -v owner="$DB_OWNER_USER" -v owner_pw="$DB_OWNER_PASSWORD" \
     -v app="$DB_APP_USER" -v app_pw="$DB_APP_PASSWORD" \
     -v db="$POSTGRES_DB" <<-'EOSQL'
	-- CREATEDB lets pytest-django create its test database as the owner.
	CREATE ROLE :"owner" LOGIN CREATEDB NOSUPERUSER NOBYPASSRLS PASSWORD :'owner_pw';
	CREATE ROLE :"app"   LOGIN NOCREATEDB NOSUPERUSER NOBYPASSRLS PASSWORD :'app_pw';

	ALTER DATABASE :"db" OWNER TO :"owner";
	REVOKE ALL ON DATABASE :"db" FROM PUBLIC;
	GRANT CONNECT, TEMPORARY ON DATABASE :"db" TO :"owner", :"app";

	ALTER SCHEMA public OWNER TO :"owner";
	REVOKE ALL ON SCHEMA public FROM PUBLIC;
	GRANT USAGE ON SCHEMA public TO :"app";

	-- Every table/sequence/function the owner creates (i.e. via migrations)
	-- is automatically usable by the app role, but only for DML.
	ALTER DEFAULT PRIVILEGES FOR ROLE :"owner" IN SCHEMA public
	    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO :"app";
	ALTER DEFAULT PRIVILEGES FOR ROLE :"owner" IN SCHEMA public
	    GRANT USAGE, SELECT ON SEQUENCES TO :"app";
	ALTER DEFAULT PRIVILEGES FOR ROLE :"owner" IN SCHEMA public
	    GRANT EXECUTE ON FUNCTIONS TO :"app";
EOSQL
