from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import Camera, Tenant, User
from .rls import set_tenant_context


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'created_at']
    search_fields = ['name', 'slug']
    prepopulated_fields = {'slug': ['name']}


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = ['username', 'email', 'tenant', 'role', 'is_staff', 'is_active']
    list_filter = ['tenant', 'role', 'is_staff', 'is_active']
    fieldsets = DjangoUserAdmin.fieldsets + (
        ('Tenancy', {'fields': ['tenant', 'role']}),
    )
    add_fieldsets = DjangoUserAdmin.add_fieldsets + (
        ('Tenancy', {'fields': ['tenant', 'role']}),
    )


class TenantScopedAdmin(admin.ModelAdmin):
    """
    Admin for an RLS-protected table. Admin views are plain Django views, so
    nothing sets the tenant context for them; without this every row would be
    invisible. Each view is scoped to the logged-in user's tenant, inside the
    request transaction (ATOMIC_REQUESTS).
    """

    def _scope(self, request):
        set_tenant_context(request.user.tenant_id)

    def changelist_view(self, request, extra_context=None):
        self._scope(request)
        return super().changelist_view(request, extra_context)

    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        self._scope(request)
        return super().changeform_view(request, object_id, form_url, extra_context)

    def delete_view(self, request, object_id, extra_context=None):
        self._scope(request)
        return super().delete_view(request, object_id, extra_context)

    def history_view(self, request, object_id, extra_context=None):
        self._scope(request)
        return super().history_view(request, object_id, extra_context)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        # Only the user's own tenant can be chosen; RLS would reject any other.
        if db_field.name == 'tenant':
            kwargs['queryset'] = Tenant.objects.filter(pk=request.user.tenant_id)
            kwargs['initial'] = request.user.tenant_id
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(Camera)
class CameraAdmin(TenantScopedAdmin):
    # Note: external_id is unique platform-wide, but the form's uniqueness
    # check can't see other tenants' cameras, so a clash with another tenant's
    # id surfaces as a database IntegrityError rather than a form error.
    list_display = ['external_id', 'label', 'tenant', 'is_active', 'created_at']
    list_filter = ['is_active']
    search_fields = ['external_id', 'label']
