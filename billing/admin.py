"""
Django Admin configuration for Billing app.

Provides admin interfaces for:
- Plans (with inline subscriptions)
- Subscriptions (with filters and actions)
- Invoices (with payment status)
- Payment Methods (with organization context)
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import Plan, Subscription, Invoice, PaymentMethod, WebhookEvent


class SubscriptionInline(admin.TabularInline):
    """
    Inline admin for displaying subscriptions within Plan admin.
    """
    model = Subscription
    extra = 0
    fields = ['organization', 'status', 'current_period_end', 'created_at']
    readonly_fields = ['organization', 'status', 'current_period_end', 'created_at']
    can_delete = False

    def get_queryset(self, request):
        """Optimize queryset with select_related"""
        return super().get_queryset(request).select_related('organization')

    def has_add_permission(self, request, obj=None):
        """Prevent adding subscriptions through inline"""
        return False


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    """
    Admin interface for Plan model.

    Features:
    - List view with pricing and status
    - Filter by gateway, interval, active status
    - Search by name, slug
    - Inline subscription display
    - Color-coded active status
    """

    list_display = [
        'name',
        'slug',
        'gateway_display',
        'price_display_formatted',
        'billing_interval',
        'subscription_count',
        'is_active_display',
        'created_at',
    ]

    list_filter = [
        'gateway',
        'billing_interval',
        'is_active',
        'created_at',
    ]

    search_fields = [
        'name',
        'slug',
        'gateway_product_id',
        'gateway_price_id',
    ]

    readonly_fields = [
        'id',
        'slug',
        'created_at',
        'updated_at',
        'subscription_count',
    ]

    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'name', 'slug', 'is_active')
        }),
        ('Pricing', {
            'fields': ('price_cents', 'billing_interval')
        }),
        ('Gateway Configuration', {
            'fields': ('gateway', 'gateway_product_id', 'gateway_price_id')
        }),
        ('Features', {
            'fields': ('features',),
            'description': 'JSON field containing feature flags and limits for this plan'
        }),
        ('Metadata', {
            'fields': ('subscription_count', 'created_at', 'updated_at')
        }),
    )

    inlines = [SubscriptionInline]

    def price_display_formatted(self, obj):
        """Display formatted price"""
        return obj.price_display
    price_display_formatted.short_description = 'Price'
    price_display_formatted.admin_order_field = 'price_cents'

    def gateway_display(self, obj):
        """Display gateway with icon"""
        gateway_icons = {
            'stripe': '💳',
            'razorpay': '💰',
            'paddle': '🏃',
        }
        icon = gateway_icons.get(obj.gateway, '💵')
        return f"{icon} {obj.get_gateway_display()}"
    gateway_display.short_description = 'Gateway'
    gateway_display.admin_order_field = 'gateway'

    def is_active_display(self, obj):
        """Display active status with color coding"""
        if obj.is_active:
            return format_html(
                '<span style="color: green; font-weight: bold;">✓ Active</span>'
            )
        return format_html(
            '<span style="color: gray; font-weight: bold;">✗ Inactive</span>'
        )
    is_active_display.short_description = 'Status'
    is_active_display.boolean = True

    def subscription_count(self, obj):
        """Display count of active subscriptions"""
        count = obj.subscriptions.filter(status__in=['active', 'trialing']).count()
        return count
    subscription_count.short_description = 'Active Subs'

    def get_queryset(self, request):
        """Optimize queryset with prefetch_related"""
        return super().get_queryset(request).prefetch_related('subscriptions')


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    """
    Admin interface for Subscription model.

    Features:
    - List view with organization, plan, status
    - Filter by status, gateway, dates
    - Search by organization, gateway IDs
    - Action to sync subscription from gateway
    - Color-coded status indicators
    """

    list_display = [
        'organization_link',
        'plan_name',
        'status_display',
        'current_period_end',
        'cancel_at_period_end',
        'gateway_display',
        'created_at',
    ]

    list_filter = [
        'status',
        'gateway',
        'cancel_at_period_end',
        'created_at',
        'current_period_end',
    ]

    search_fields = [
        'organization__name',
        'organization__slug',
        'plan__name',
        'gateway_subscription_id',
        'gateway_customer_id',
    ]

    readonly_fields = [
        'id',
        'organization',
        'plan',
        'gateway',
        'gateway_subscription_id',
        'gateway_customer_id',
        'created_at',
        'updated_at',
    ]

    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'organization', 'plan')
        }),
        ('Gateway Details', {
            'fields': ('gateway', 'gateway_subscription_id', 'gateway_customer_id')
        }),
        ('Status', {
            'fields': ('status', 'cancel_at_period_end', 'cancelled_at')
        }),
        ('Billing Period', {
            'fields': ('current_period_start', 'current_period_end', 'trial_end')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at')
        }),
    )

    actions = ['sync_from_gateway']

    def organization_link(self, obj):
        """Display organization with link"""
        url = reverse('admin:organizations_organization_change', args=[obj.organization.id])
        return format_html('<a href="{}">{}</a>', url, obj.organization.name)
    organization_link.short_description = 'Organization'
    organization_link.admin_order_field = 'organization__name'

    def plan_name(self, obj):
        """Display plan name"""
        return obj.plan.name
    plan_name.short_description = 'Plan'
    plan_name.admin_order_field = 'plan__name'

    def status_display(self, obj):
        """Display status with color coding"""
        status_colors = {
            'active': 'green',
            'trialing': 'blue',
            'cancelled': 'gray',
            'past_due': 'orange',
            'unpaid': 'red',
            'incomplete': 'yellow',
        }
        color = status_colors.get(obj.status, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_display.short_description = 'Status'
    status_display.admin_order_field = 'status'

    def gateway_display(self, obj):
        """Display gateway"""
        return obj.get_gateway_display() if hasattr(obj, 'get_gateway_display') else obj.gateway
    gateway_display.short_description = 'Gateway'
    gateway_display.admin_order_field = 'gateway'

    def sync_from_gateway(self, request, queryset):
        """Action to sync selected subscriptions from gateway"""
        from .services import BillingService
        from .gateways.base import GatewayException
        from django.contrib import messages

        MAX_SYNC_PER_REQUEST = 50

        # Check if too many subscriptions selected
        count = queryset.count()
        if count > MAX_SYNC_PER_REQUEST:
            self.message_user(
                request,
                f"Cannot sync more than {MAX_SYNC_PER_REQUEST} subscriptions at once. "
                f"You selected {count}. Please select fewer items.",
                level=messages.ERROR
            )
            return

        synced = 0
        failed = 0

        for subscription in queryset:
            try:
                BillingService.sync_subscription_from_gateway(subscription)
                synced += 1
            except GatewayException:
                failed += 1

        self.message_user(
            request,
            f"Synced {synced} subscription(s). {failed} failed."
        )
    sync_from_gateway.short_description = "Sync selected subscriptions from gateway"

    def get_queryset(self, request):
        """Optimize queryset with select_related"""
        return super().get_queryset(request).select_related('organization', 'plan')


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    """
    Admin interface for Invoice model.

    Features:
    - List view with organization, amount, status
    - Filter by status, gateway, dates
    - Search by organization, gateway IDs
    - Color-coded payment status
    - Link to invoice URL
    """

    list_display = [
        'gateway_invoice_id',
        'organization_link',
        'amount_display_formatted',
        'status_display',
        'issued_at',
        'paid_at',
        'invoice_link',
    ]

    list_filter = [
        'status',
        'gateway',
        'issued_at',
        'paid_at',
        'created_at',
    ]

    search_fields = [
        'gateway_invoice_id',
        'organization__name',
        'organization__slug',
        'subscription__gateway_subscription_id',
    ]

    readonly_fields = [
        'id',
        'organization',
        'subscription',
        'gateway',
        'gateway_invoice_id',
        'amount_cents',
        'currency',
        'status',
        'issued_at',
        'paid_at',
        'invoice_url',
        'created_at',
        'updated_at',
    ]

    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'organization', 'subscription')
        }),
        ('Gateway Details', {
            'fields': ('gateway', 'gateway_invoice_id')
        }),
        ('Payment Details', {
            'fields': ('amount_cents', 'currency', 'status')
        }),
        ('Timestamps', {
            'fields': ('issued_at', 'paid_at', 'created_at', 'updated_at')
        }),
        ('Invoice URL', {
            'fields': ('invoice_url',)
        }),
    )

    def organization_link(self, obj):
        """Display organization with link"""
        url = reverse('admin:organizations_organization_change', args=[obj.organization.id])
        return format_html('<a href="{}">{}</a>', url, obj.organization.name)
    organization_link.short_description = 'Organization'
    organization_link.admin_order_field = 'organization__name'

    def amount_display_formatted(self, obj):
        """Display formatted amount"""
        return obj.amount_display
    amount_display_formatted.short_description = 'Amount'
    amount_display_formatted.admin_order_field = 'amount_cents'

    def status_display(self, obj):
        """Display status with color coding"""
        status_colors = {
            'paid': 'green',
            'open': 'orange',
            'draft': 'gray',
            'void': 'gray',
            'uncollectible': 'red',
        }
        status_icons = {
            'paid': '✓',
            'open': '⧗',
            'draft': '📝',
            'void': '✗',
            'uncollectible': '✗',
        }
        color = status_colors.get(obj.status, 'gray')
        icon = status_icons.get(obj.status, '•')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{} {}</span>',
            color,
            icon,
            obj.get_status_display()
        )
    status_display.short_description = 'Status'
    status_display.admin_order_field = 'status'

    def invoice_link(self, obj):
        """Display link to invoice URL if available"""
        if obj.invoice_url:
            return format_html(
                '<a href="{}" target="_blank">View Invoice</a>',
                obj.invoice_url
            )
        return '-'
    invoice_link.short_description = 'Invoice'

    def get_queryset(self, request):
        """Optimize queryset with select_related"""
        return super().get_queryset(request).select_related(
            'organization',
            'subscription',
            'subscription__plan'
        )


@admin.register(PaymentMethod)
class PaymentMethodAdmin(admin.ModelAdmin):
    """
    Admin interface for PaymentMethod model.

    Features:
    - List view with organization, type, brand
    - Filter by type, gateway, default status
    - Search by organization, gateway IDs
    - Color-coded default status
    """

    list_display = [
        'organization_link',
        'type_display_formatted',
        'brand',
        'last4',
        'is_default_display',
        'gateway',
        'created_at',
    ]

    list_filter = [
        'type',
        'gateway',
        'is_default',
        'created_at',
    ]

    search_fields = [
        'organization__name',
        'organization__slug',
        'gateway_payment_method_id',
        'brand',
        'last4',
    ]

    readonly_fields = [
        'id',
        'organization',
        'gateway',
        'gateway_payment_method_id',
        'type',
        'last4',
        'brand',
        'created_at',
        'updated_at',
    ]

    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'organization', 'is_default')
        }),
        ('Gateway Details', {
            'fields': ('gateway', 'gateway_payment_method_id')
        }),
        ('Payment Method Details', {
            'fields': ('type', 'brand', 'last4')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at')
        }),
    )

    def organization_link(self, obj):
        """Display organization with link"""
        url = reverse('admin:organizations_organization_change', args=[obj.organization.id])
        return format_html('<a href="{}">{}</a>', url, obj.organization.name)
    organization_link.short_description = 'Organization'
    organization_link.admin_order_field = 'organization__name'

    def type_display_formatted(self, obj):
        """Display type with icon"""
        type_icons = {
            'card': '💳',
            'bank_account': '🏦',
            'upi': '📱',
            'wallet': '👛',
        }
        icon = type_icons.get(obj.type, '💵')
        return f"{icon} {obj.get_type_display()}"
    type_display_formatted.short_description = 'Type'
    type_display_formatted.admin_order_field = 'type'

    def is_default_display(self, obj):
        """Display default status with color coding"""
        if obj.is_default:
            return format_html(
                '<span style="color: green; font-weight: bold;">⭐ Default</span>'
            )
        return format_html('<span style="color: gray;">-</span>')
    is_default_display.short_description = 'Default'
    is_default_display.boolean = True

    def get_queryset(self, request):
        """Optimize queryset with select_related"""
        return super().get_queryset(request).select_related('organization')


@admin.register(WebhookEvent)
class WebhookEventAdmin(admin.ModelAdmin):
    """
    Admin interface for WebhookEvent model.
    Provides read-only view of processed webhook events for debugging and auditing.
    """
    list_display = [
        'event_id',
        'event_type',
        'gateway',
        'processed_at',
        'created_at'
    ]
    list_filter = [
        'gateway',
        'event_type',
        'processed_at',
        'created_at'
    ]
    search_fields = [
        'event_id',
        'event_type',
        'gateway'
    ]
    readonly_fields = [
        'id',
        'event_id',
        'event_type',
        'gateway',
        'processed_at',
        'payload',
        'created_at'
    ]
    ordering = ['-created_at']
    date_hierarchy = 'created_at'

    def has_add_permission(self, request):
        """Webhook events are created automatically, not manually"""
        return False

    def has_delete_permission(self, request, obj=None):
        """Allow deletion for cleanup purposes"""
        return True

    def has_change_permission(self, request, obj=None):
        """Webhook events should not be modified"""
        return False
