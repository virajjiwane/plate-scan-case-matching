import uuid

from django.contrib.auth.models import AbstractUser, UserManager as DjangoUserManager
from django.db import models


class Tenant(models.Model):
    """A recovery agency. Every user, camera and scan belongs to exactly one."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'tenants'
        ordering = ['name']

    def __str__(self):
        return self.name


class UserManager(DjangoUserManager):
    def _create_user(self, username, email, password, **extra_fields):
        # `createsuperuser` passes the tenant as a raw primary key.
        tenant = extra_fields.get('tenant')
        if tenant is not None and not isinstance(tenant, Tenant):
            extra_fields['tenant'] = Tenant.objects.get(pk=tenant)
        return super()._create_user(username, email, password, **extra_fields)


class User(AbstractUser):
    """
    A staff member of one tenant.

    The tenant is never taken from the JWT or any other client input; it is
    always read from this row on the server.
    """

    class Role(models.TextChoices):
        STAFF = 'staff', 'Staff'
        ADMIN = 'admin', 'Admin'

    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, related_name='users')
    role = models.CharField(max_length=16, choices=Role.choices, default=Role.STAFF)

    # Prompted for by `createsuperuser` (expects the tenant's UUID).
    REQUIRED_FIELDS = ['email', 'tenant']

    objects = UserManager()

    class Meta:
        db_table = 'users'

    @property
    def is_tenant_admin(self):
        return self.role == self.Role.ADMIN


class Camera(models.Model):
    """
    An LPR camera. The unauthenticated scan webhook identifies itself only by
    `external_id`, which is how an incoming scan is attributed to a tenant.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    external_id = models.CharField(max_length=64, unique=True)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, related_name='cameras')
    label = models.CharField(max_length=200, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'cameras'
        ordering = ['external_id']

    def __str__(self):
        return self.external_id
