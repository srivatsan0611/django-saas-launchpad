from django.contrib import admin

from .models import Event, DailyMetric, MonthlyMetric, FeatureMetric

@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    """
    Read-only admin view for tracking user events.
    Provides a read-only view of events for an organization.
    """
    list_display = (
        "id",
        "organization",
        "user",
        "name",
        "timestamp",
        "received_at",
        "ip_address",
        "user_agent"
    )
    list_filter = (
        "organization",
        "user",
        "name",
        "timestamp",
        "received_at",
        "ip_address",
        "user_agent"
    )
    search_fields = (
        "name",
        "user__username",
        "organization__name",
        "ip_address",
        "user_agent"
    )
    ordering = ("-timestamp",)
    readonly_fields = (
        "organization",
        "user",
        "name",
        "properties",
        "timestamp",
        "received_at",
        "ip_address",
        "user_agent"
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

@admin.register(DailyMetric)
class DailyMetricAdmin(admin.ModelAdmin):
    """
    Read-only admin view for daily metrics.
    Provides a read-only view of daily metrics for an organization.
    """
    list_display = (
        "organization",
        "date",
        "dau",
        "new_users",
        "revenue_cents"
    )
    list_filter = (
        "organization",
        "date",
        "dau",
        "new_users"
    )
    search_fields = (
        "organization__name",
    )
    ordering = ("-date",)
    readonly_fields = (
        "organization",
         "date",
         "dau",   
         "new_users",
         "revenue_cents"
        )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(MonthlyMetric)
class MonthlyMetricAdmin(admin.ModelAdmin):
    """
    Read-only admin view for monthly metrics.
    Provides a read-only view of monthly metrics for an organization.
    """
    list_display = (
        "organization",
         "year",
         "month",
         "mau",
         "mrr_cents", 
         "churn_rate"
        )
    list_filter = (
        "organization", 
        "year",
        "month"
    )
    search_fields = ("organization__name",)
    ordering = ("-year", "-month")
    readonly_fields = (
        "organization",
         "year",
         "month",
         "mau",
         "mrr_cents",
         "churn_rate"
        )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(FeatureMetric)
class FeatureMetricAdmin(admin.ModelAdmin):
    """
    Read-only admin view for feature metrics.
    Provides a read-only view of feature metrics for an organization.
    """
    list_display = (
        "organization",
         "feature_name",
         "date",
         "usage_count",
        )

    list_filter = (
        "organization",
        "feature_name",
        "date",
    )
    search_fields = (
        "organization__name",
        "feature_name",
        "date",
    )
    
    ordering = ("-date",)
    readonly_fields = (
        "organization",
         "feature_name",
         "date",
         "usage_count",
        )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
