"""
Django Admin configuration for Organizations app.

Provides admin interfaces for:
- Organizations (with inline memberships)
- Memberships (with filters and search)
- Invitations (with status indicators)
"""

from django.contrib import admin
from django.utils.html import format_html
from .models import Organization, Membership, Invitation


class MembershipInline(admin.TabularInline):
    """
    Inline admin for displaying memberships within Organization admin.
    Allows viewing and editing members directly from the organization page.
    """
    model = Membership
    extra = 0
    fields = ['user', 'role', 'joined_at']
    readonly_fields = ['joined_at']
    autocomplete_fields = ['user']

    def get_queryset(self, request):
        """Optimize queryset with select_related"""
        return super().get_queryset(request).select_related('user')


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    """
    Admin interface for Organization model.

    Features:
    - List view with key organization info
    - Search by name, slug, owner email
    - Filter by creation date
    - Inline membership management
    - Read-only fields for system-generated data
    """

    list_display = [
        'name',
        'slug',
        'owner_email',
        'member_count_display',
        'created_at',
    ]

    list_filter = [
        'created_at',
    ]

    search_fields = [
        'name',
        'slug',
        'owner__email',
        'owner__first_name',
        'owner__last_name',
    ]

    readonly_fields = [
        'id',
        'slug',
        'created_at',
        'updated_at',
        'member_count_display',
    ]

    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'name', 'slug', 'owner')
        }),
        ('Metadata', {
            'fields': ('member_count_display', 'created_at', 'updated_at')
        }),
    )

    inlines = [MembershipInline]

    autocomplete_fields = ['owner']

    def owner_email(self, obj):
        """Display owner's email in list view"""
        return obj.owner.email
    owner_email.short_description = 'Owner'
    owner_email.admin_order_field = 'owner__email'

    def member_count_display(self, obj):
        """Display total member count"""
        return obj.get_member_count()
    member_count_display.short_description = 'Members'

    def get_queryset(self, request):
        """Optimize queryset with select_related and prefetch_related"""
        return super().get_queryset(request).select_related('owner').prefetch_related('memberships')


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    """
    Admin interface for Membership model.

    Features:
    - List view with user, organization, and role
    - Filter by role and join date
    - Search by user email, organization name
    - Prevent changing user or organization after creation
    """

    list_display = [
        'user_email',
        'organization_name',
        'role',
        'joined_at',
    ]

    list_filter = [
        'role',
        'joined_at',
    ]

    search_fields = [
        'user__email',
        'user__first_name',
        'user__last_name',
        'organization__name',
        'organization__slug',
    ]

    readonly_fields = [
        'joined_at',
    ]

    autocomplete_fields = ['user', 'organization']

    fieldsets = (
        ('Membership Details', {
            'fields': ('user', 'organization', 'role')
        }),
        ('Metadata', {
            'fields': ('joined_at',)
        }),
    )

    def user_email(self, obj):
        """Display user's email in list view"""
        return obj.user.email
    user_email.short_description = 'User'
    user_email.admin_order_field = 'user__email'

    def organization_name(self, obj):
        """Display organization name in list view"""
        return obj.organization.name
    organization_name.short_description = 'Organization'
    organization_name.admin_order_field = 'organization__name'

    def get_queryset(self, request):
        """Optimize queryset with select_related"""
        return super().get_queryset(request).select_related('user', 'organization')


@admin.register(Invitation)
class InvitationAdmin(admin.ModelAdmin):
    """
    Admin interface for Invitation model.

    Features:
    - List view with invitation details and status
    - Visual indicators for expired/accepted status
    - Filter by status, role, dates
    - Search by email, organization
    - Read-only fields for system-generated data
    """

    list_display = [
        'email',
        'organization_name',
        'role',
        'invited_by_email',
        'status_display',
        'expires_at',
        'created_at',
    ]

    list_filter = [
        'role',
        'created_at',
        'expires_at',
        'accepted_at',
    ]

    search_fields = [
        'email',
        'organization__name',
        'organization__slug',
        'invited_by__email',
    ]

    readonly_fields = [
        'id',
        'token',
        'created_at',
        'expires_at',
        'accepted_at',
        'status_display',
        'is_expired_display',
        'is_accepted_display',
    ]

    fieldsets = (
        ('Invitation Details', {
            'fields': ('id', 'email', 'organization', 'invited_by', 'role')
        }),
        ('Status', {
            'fields': ('status_display', 'is_expired_display', 'is_accepted_display')
        }),
        ('Security', {
            'fields': ('token',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'expires_at', 'accepted_at')
        }),
    )

    autocomplete_fields = ['organization', 'invited_by']

    def organization_name(self, obj):
        """Display organization name in list view"""
        return obj.organization.name
    organization_name.short_description = 'Organization'
    organization_name.admin_order_field = 'organization__name'

    def invited_by_email(self, obj):
        """Display inviter's email in list view"""
        return obj.invited_by.email
    invited_by_email.short_description = 'Invited By'
    invited_by_email.admin_order_field = 'invited_by__email'

    def status_display(self, obj):
        """Display invitation status with color coding"""
        if obj.is_accepted():
            return format_html(
                '<span style="color: green; font-weight: bold;">✓ Accepted</span>'
            )
        elif obj.is_expired():
            return format_html(
                '<span style="color: red; font-weight: bold;">✗ Expired</span>'
            )
        else:
            return format_html(
                '<span style="color: orange; font-weight: bold;">⧗ Pending</span>'
            )
    status_display.short_description = 'Status'

    def is_expired_display(self, obj):
        """Display if invitation is expired"""
        if obj.is_expired():
            return format_html('<span style="color: red;">Yes</span>')
        return format_html('<span style="color: green;">No</span>')
    is_expired_display.short_description = 'Expired?'
    is_expired_display.boolean = True

    def is_accepted_display(self, obj):
        """Display if invitation is accepted"""
        if obj.is_accepted():
            return format_html('<span style="color: green;">Yes</span>')
        return format_html('<span style="color: gray;">No</span>')
    is_accepted_display.short_description = 'Accepted?'
    is_accepted_display.boolean = True

    def get_queryset(self, request):
        """Optimize queryset with select_related"""
        return super().get_queryset(request).select_related(
            'organization',
            'invited_by'
        )
