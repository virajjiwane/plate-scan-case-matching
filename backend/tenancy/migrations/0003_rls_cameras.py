from django.db import migrations

# Runs as the owner role. RLS is ENABLEd but not FORCEd: the owner (migrations,
# SECURITY DEFINER functions) bypasses it, the runtime app role never does.
#
# NULLIF(..., ''): after a transaction that set app.tenant_id ends, the setting
# reads back as '' rather than NULL, and ''::uuid would raise. With NULLIF an
# unset context simply matches no rows.

FORWARD = """
ALTER TABLE cameras ENABLE ROW LEVEL SECURITY;

CREATE POLICY cameras_tenant_isolation ON cameras
    USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

-- The unauthenticated scan webhook must map an external camera id to its
-- tenant before any tenant context exists. Exposes only what ingest needs.
CREATE FUNCTION resolve_camera(p_external_id text)
RETURNS TABLE (id uuid, tenant_id uuid, is_active boolean)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
    SELECT c.id, c.tenant_id, c.is_active
    FROM cameras c
    WHERE c.external_id = p_external_id
$$;

-- Functions are executable by PUBLIC by default; the app role is granted
-- EXECUTE through the owner's default privileges (db/init/01-roles.sh).
REVOKE ALL ON FUNCTION resolve_camera(text) FROM PUBLIC;
"""

REVERSE = """
DROP FUNCTION IF EXISTS resolve_camera(text);
DROP POLICY IF EXISTS cameras_tenant_isolation ON cameras;
ALTER TABLE cameras DISABLE ROW LEVEL SECURITY;
"""


class Migration(migrations.Migration):

    dependencies = [
        ('tenancy', '0002_alter_user_managers'),
    ]

    operations = [
        migrations.RunSQL(FORWARD, REVERSE),
    ]
