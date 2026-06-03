"""
Django Admin configuration for Feature Flags app.

Provides admin interfaces for:
- Feature Flags (with toggle actions, search, and filters)
"""

import json

from django.contrib import admin, messages
from django.utils.html import format_html

from .models import FeatureFlag


@admin.register(FeatureFlag)
class FeatureFlagAdmin(admin.ModelAdmin):
    """
    Admin interface for FeatureFlag model.

    Features:
    - List view with key flag information
    - Toggle actions to enable/disable flags
    - Search by key, name, description
    - Filter by enabled status, organization, creation date
    - Visual status indicators
    - Read-only fields for system-generated data
    """

    list_display = [
        "key",
        "name",
        "organization_display",
        "enabled_status",
        "enabled",  # Added for list_editable
        "default_enabled",
        "has_rules",
        "created_at",
        "updated_at",
    ]

    list_filter = [
        "enabled",
        "default_enabled",
        "organization",
        "created_at",
        "updated_at",
    ]

    search_fields = [
        "key",
        "name",
        "description",
        "organization__name",
        "organization__slug",
    ]

    readonly_fields = [
        "id",
        "created_at",
        "updated_at",
        "enabled_status",
        "is_global_display",
        "rules_display",
    ]

    fieldsets = (
        (
            "Basic Information",
            {"fields": ("id", "key", "name", "description", "organization")},
        ),
        (
            "Status",
            {
                "fields": (
                    "default_enabled",
                    "enabled",
                    "enabled_status",
                    "is_global_display",
                )
            },
        ),
        (
            "Rules",
            {
                "fields": ("rules", "rules_display"),
                "description": "JSON object containing feature flag rules (e.g., rollout_percentage, whitelist)",
            },
        ),
        ("Metadata", {"fields": ("created_at", "updated_at")}),
    )

    list_editable = ["enabled"]

    actions = ["enable_flags", "disable_flags", "toggle_flags"]

    autocomplete_fields = ["organization"]

    def organization_display(self, obj):
        """Display organization name or 'Global' for global flags"""
        if obj.organization:
            return obj.organization.name
        return format_html(
            '<span style="color: blue; font-weight: bold;">Global</span>'
        )

    organization_display.short_description = "Organization"
    organization_display.admin_order_field = "organization__name"

    def enabled_status(self, obj):
        """Display enabled status with color coding"""
        if obj.enabled:
            return format_html(
                '<span style="color: green; font-weight: bold;">✓ Enabled</span>'
            )
        return format_html(
            '<span style="color: red; font-weight: bold;">✗ Disabled</span>'
        )

    enabled_status.short_description = "Status"
    enabled_status.boolean = True

    def is_global_display(self, obj):
        """Display if flag is global"""
        if obj.is_global():
            return format_html(
                '<span style="color: blue;">Yes (applies to all organizations)</span>'
            )
        return format_html(
            '<span style="color: gray;">No (organization-specific)</span>'
        )

    is_global_display.short_description = "Is Global?"
    is_global_display.boolean = True

    def has_rules(self, obj):
        """Display if flag has rules configured"""
        if obj.rules and isinstance(obj.rules, dict) and obj.rules:
            rule_keys = ", ".join(obj.rules.keys())
            return format_html(
                '<span style="color: orange;" title="{}">Yes ({})</span>',
                rule_keys,
                rule_keys,
            )
        return format_html('<span style="color: gray;">No</span>')

    has_rules.short_description = "Has Rules"
    has_rules.boolean = True

    def rules_display(self, obj):
        """Display rules in a formatted way"""
        if obj.rules and isinstance(obj.rules, dict) and obj.rules:
            formatted_rules = json.dumps(obj.rules, indent=2)
            return format_html(
                '<pre style="background: #f5f5f5; padding: 10px; border-radius: 4px;">{}</pre>',
                formatted_rules,
            )
        return format_html('<span style="color: gray;">No rules configured</span>')

    rules_display.short_description = "Rules (Formatted)"

    def enable_flags(self, request, queryset):
        """Action to enable selected flags"""
        count = queryset.update(enabled=True)
        self.message_user(
            request, f"Successfully enabled {count} feature flag(s).", messages.SUCCESS
        )

    enable_flags.short_description = "Enable selected flags"

    def disable_flags(self, request, queryset):
        """Action to disable selected flags"""
        count = queryset.update(enabled=False)
        self.message_user(
            request, f"Successfully disabled {count} feature flag(s).", messages.SUCCESS
        )

    disable_flags.short_description = "Disable selected flags"

    def toggle_flags(self, request, queryset):
        """Action to toggle enabled status of selected flags"""
        updated = []
        for flag in queryset:
            flag.enabled = not flag.enabled
            flag.save(update_fields=["enabled"])
            updated.append(flag)

        count = len(updated)
        self.message_user(
            request, f"Successfully toggled {count} feature flag(s).", messages.SUCCESS
        )

    toggle_flags.short_description = "Toggle enabled status of selected flags"

    def get_queryset(self, request):
        """Optimize queryset with select_related"""
        return super().get_queryset(request).select_related("organization")

    def save_model(self, request, obj, form, change):
        """Override save to add custom logic if needed"""
        super().save_model(request, obj, form, change)

        # Log message if this is a global flag
        if obj.is_global():
            self.message_user(
                request,
                f'Global flag "{obj.key}" saved. This will apply to all organizations unless overridden.',
                messages.INFO,
            )
