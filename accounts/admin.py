from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from django.utils.html import format_html

from .models import User, MagicLink


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """
    Custom admin interface for User model with email-based authentication.
    Provides comprehensive management of user accounts including verification status.
    """

    # Fields to display in the list view
    list_display = (
        'email',
        'first_name',
        'last_name',
        'is_active',
        'email_verified_badge',
        'is_staff',
        'is_superuser',
        'created_at',
        'last_login'
    )

    # Filters for the sidebar
    list_filter = (
        'is_staff',
        'is_superuser',
        'is_active',
        'email_verified',
        'created_at',
        'last_login'
    )

    # Fields to search
    search_fields = ('email', 'first_name', 'last_name')

    # Default ordering
    ordering = ('-created_at',)

    # Fields that are read-only
    readonly_fields = (
        'created_at',
        'updated_at',
        'last_login',
        'date_joined',
        'email_verification_token',
        'password_reset_token',
        'password_reset_token_expires_at'
    )

    # Custom fieldsets for the detail/edit view
    fieldsets = (
        (None, {
            'fields': ('email', 'password')
        }),
        (_('Personal Info'), {
            'fields': ('first_name', 'last_name')
        }),
        (_('Email Verification'), {
            'fields': (
                'email_verified',
                'email_verification_token'
            ),
            'classes': ('collapse',)
        }),
        (_('Password Reset'), {
            'fields': (
                'password_reset_token',
                'password_reset_token_expires_at'
            ),
            'classes': ('collapse',)
        }),
        (_('Permissions'), {
            'fields': (
                'is_active',
                'is_staff',
                'is_superuser',
                'groups',
                'user_permissions'
            ),
        }),
        (_('Important Dates'), {
            'fields': (
                'last_login',
                'date_joined',
                'created_at',
                'updated_at'
            ),
        }),
    )

    # Fieldsets for adding a new user
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'email',
                'password1',
                'password2',
                'first_name',
                'last_name',
                'is_active',
                'is_staff',
                'is_superuser'
            ),
        }),
    )

    def email_verified_badge(self, obj):
        """
        Display a colored badge for email verification status.

        Args:
            obj: User instance

        Returns:
            HTML formatted badge showing verification status
        """
        if obj.email_verified:
            return format_html(
                '<span style="background-color: #28a745; color: white; '
                'padding: 3px 10px; border-radius: 3px; font-weight: bold;">'
                'Verified</span>'
            )
        return format_html(
            '<span style="background-color: #dc3545; color: white; '
            'padding: 3px 10px; border-radius: 3px; font-weight: bold;">'
            'Unverified</span>'
        )

    email_verified_badge.short_description = _('Email Status')


@admin.register(MagicLink)
class MagicLinkAdmin(admin.ModelAdmin):
    """
    Admin interface for MagicLink model.
    Provides read-only view of magic links for passwordless authentication.
    """

    # Fields to display in the list view
    list_display = (
        'user',
        'token_short',
        'created_at',
        'expires_at',
        'is_used',
        'validity_status'
    )

    # Filters for the sidebar
    list_filter = (
        'is_used',
        'created_at',
        'expires_at'
    )

    # Fields to search
    search_fields = ('user__email', 'token')

    # Default ordering
    ordering = ('-created_at',)

    # Fields that are read-only (magic links should not be edited)
    readonly_fields = (
        'user',
        'token',
        'created_at',
        'expires_at',
        'is_used',
        'validity_status_display'
    )

    # Fieldsets for the detail view
    fieldsets = (
        (_('Magic Link Details'), {
            'fields': (
                'user',
                'token',
                'validity_status_display'
            )
        }),
        (_('Status'), {
            'fields': (
                'is_used',
                'created_at',
                'expires_at'
            )
        }),
    )

    def has_add_permission(self, request):
        """
        Disable manual creation of magic links through admin.
        Magic links should only be created through the API.
        """
        return False

    def has_change_permission(self, request, obj=None):
        """
        Disable editing of magic links.
        Magic links are immutable once created.
        """
        return False

    def token_short(self, obj):
        """
        Display shortened version of the token for list view.

        Args:
            obj: MagicLink instance

        Returns:
            Shortened token string
        """
        return f"{str(obj.token)[:8]}..."

    token_short.short_description = _('Token')

    def validity_status(self, obj):
        """
        Display colored badge for magic link validity status.

        Args:
            obj: MagicLink instance

        Returns:
            HTML formatted badge showing validity status
        """
        if obj.is_used:
            return format_html(
                '<span style="background-color: #6c757d; color: white; '
                'padding: 3px 10px; border-radius: 3px; font-weight: bold;">'
                'Used</span>'
            )
        elif obj.is_expired():
            return format_html(
                '<span style="background-color: #dc3545; color: white; '
                'padding: 3px 10px; border-radius: 3px; font-weight: bold;">'
                'Expired</span>'
            )
        return format_html(
            '<span style="background-color: #28a745; color: white; '
            'padding: 3px 10px; border-radius: 3px; font-weight: bold;">'
            'Valid</span>'
        )

    validity_status.short_description = _('Status')

    def validity_status_display(self, obj):
        """
        Display detailed validity status for detail view.

        Args:
            obj: MagicLink instance

        Returns:
            HTML formatted status information
        """
        if obj.is_used:
            status = 'Used'
            color = '#6c757d'
        elif obj.is_expired():
            status = 'Expired'
            color = '#dc3545'
        else:
            status = 'Valid'
            color = '#28a745'

        return format_html(
            '<div style="padding: 10px; background-color: {}; color: white; '
            'border-radius: 5px; font-weight: bold; text-align: center;">'
            '{}</div>',
            color, status
        )

    validity_status_display.short_description = _('Validity Status')
