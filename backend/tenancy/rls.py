"""
Postgres row-level security (RLS) tenant context.

RLS policies read the current tenant from the `app.tenant_id` setting. It is
always set transaction-locally (`set_config(..., true)`), so it disappears at
COMMIT/ROLLBACK and cannot leak between requests that share a connection.

Only the runtime role (app_rw) is subject to RLS. The owner role, used for
migrations and by SECURITY DEFINER functions, is not.
"""

from contextlib import contextmanager
from dataclasses import dataclass
from uuid import UUID

from django.db import connection, transaction

SETTING = 'app.tenant_id'


def set_tenant_context(tenant_id):
    """Scope the current transaction to `tenant_id`. Must run inside one."""
    if not connection.in_atomic_block:
        raise RuntimeError(
            'Tenant context must be set inside a transaction; '
            'outside one it would be discarded immediately.'
        )
    with connection.cursor() as cursor:
        cursor.execute('SELECT set_config(%s, %s, true)', [SETTING, str(tenant_id)])


def current_tenant_id():
    """The tenant the current transaction is scoped to, or None."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT NULLIF(current_setting(%s, true), '')", [SETTING])
        value = cursor.fetchone()[0]
    return UUID(value) if value else None


@contextmanager
def tenant_context(tenant_id):
    """
    Run a block scoped to `tenant_id`, for code outside the request cycle
    (ingest, management commands, tests). Restores the previous context on
    exit, so nesting inside another transaction doesn't leak the scope.
    """
    with transaction.atomic():
        previous = current_tenant_id()
        set_tenant_context(tenant_id)
        yield
        # Only reached on success. On error, atomic() rolls back (to its
        # savepoint when nested), which undoes the set_config as well.
        with connection.cursor() as cursor:
            cursor.execute(
                'SELECT set_config(%s, %s, true)',
                [SETTING, str(previous) if previous else ''],
            )


@dataclass(frozen=True)
class ResolvedCamera:
    id: UUID
    tenant_id: UUID
    is_active: bool


def resolve_camera(external_id):
    """
    Look up a camera by external id *before* any tenant is known (the scan
    webhook is unauthenticated). RLS would hide the row, so this goes through
    the SECURITY DEFINER function `resolve_camera`, which exposes only the
    fields needed to attribute the scan. Returns None if unknown.
    """
    with connection.cursor() as cursor:
        cursor.execute('SELECT id, tenant_id, is_active FROM resolve_camera(%s)', [external_id])
        row = cursor.fetchone()
    return ResolvedCamera(*row) if row else None
