from rest_framework import serializers
from .models import Plan, Subscription, Invoice, PaymentMethod
from organizations.models import Organization


class PlanSerializer(serializers.ModelSerializer):
    """
    Serializer for billing plan data.
    Includes formatted price display and feature information.
    """
    price_display = serializers.ReadOnlyField()
    billing_interval_display = serializers.CharField(
        source='get_billing_interval_display',
        read_only=True
    )
    gateway_display = serializers.CharField(
        source='get_gateway_display',
        read_only=True
    )

    class Meta:
        model = Plan
        fields = [
            'id',
            'name',
            'slug',
            'gateway',
            'gateway_display',
            'price_cents',
            'price_display',
            'billing_interval',
            'billing_interval_display',
            'features',
            'is_active',
            'created_at',
            'updated_at'
        ]
        read_only_fields = [
            'id',
            'slug',
            'created_at',
            'updated_at',
            'price_display',
            'billing_interval_display',
            'gateway_display'
        ]


class SubscriptionSerializer(serializers.ModelSerializer):
    """
    Serializer for subscription data.
    Includes plan details and organization info.
    """
    plan = PlanSerializer(read_only=True)
    organization_name = serializers.CharField(
        source='organization.name',
        read_only=True
    )
    status_display = serializers.CharField(
        source='get_status_display',
        read_only=True
    )
    is_active = serializers.SerializerMethodField()
    is_trialing = serializers.SerializerMethodField()

    class Meta:
        model = Subscription
        fields = [
            'id',
            'organization_name',
            'plan',
            'gateway',
            'gateway_subscription_id',
            'gateway_customer_id',
            'status',
            'status_display',
            'current_period_start',
            'current_period_end',
            'trial_end',
            'cancel_at_period_end',
            'cancelled_at',
            'created_at',
            'updated_at',
            'is_active',
            'is_trialing'
        ]
        read_only_fields = [
            'id',
            'organization_name',
            'gateway_subscription_id',
            'gateway_customer_id',
            'status',
            'status_display',
            'current_period_start',
            'current_period_end',
            'trial_end',
            'cancelled_at',
            'created_at',
            'updated_at',
            'is_active',
            'is_trialing'
        ]

    def get_is_active(self, obj):
        """Check if subscription is currently active"""
        return obj.is_active()

    def get_is_trialing(self, obj):
        """Check if subscription is in trial period"""
        return obj.is_trialing()


class InvoiceSerializer(serializers.ModelSerializer):
    """
    Serializer for invoice data.
    Includes formatted amount display and organization info.
    """
    organization_name = serializers.CharField(
        source='organization.name',
        read_only=True
    )
    amount_display = serializers.ReadOnlyField()
    status_display = serializers.CharField(
        source='get_status_display',
        read_only=True
    )
    is_paid = serializers.SerializerMethodField()

    class Meta:
        model = Invoice
        fields = [
            'id',
            'organization_name',
            'subscription',
            'gateway',
            'gateway_invoice_id',
            'amount_cents',
            'amount_display',
            'currency',
            'status',
            'status_display',
            'issued_at',
            'paid_at',
            'invoice_url',
            'created_at',
            'updated_at',
            'is_paid'
        ]
        read_only_fields = [
            'id',
            'organization_name',
            'gateway_invoice_id',
            'amount_display',
            'status',
            'status_display',
            'issued_at',
            'paid_at',
            'invoice_url',
            'created_at',
            'updated_at',
            'is_paid'
        ]

    def get_is_paid(self, obj):
        """Check if invoice has been paid"""
        return obj.is_paid()


class PaymentMethodSerializer(serializers.ModelSerializer):
    """
    Serializer for payment method data.
    Includes organization info and type display.
    """
    organization_name = serializers.CharField(
        source='organization.name',
        read_only=True
    )
    type_display = serializers.CharField(
        source='get_type_display',
        read_only=True
    )

    class Meta:
        model = PaymentMethod
        fields = [
            'id',
            'organization_name',
            'gateway',
            'gateway_payment_method_id',
            'type',
            'type_display',
            'last4',
            'brand',
            'is_default',
            'created_at',
            'updated_at'
        ]
        read_only_fields = [
            'id',
            'organization_name',
            'gateway_payment_method_id',
            'type',
            'type_display',
            'last4',
            'brand',
            'created_at',
            'updated_at'
        ]


class CreateCheckoutSessionSerializer(serializers.Serializer):
    """
    Serializer for creating a checkout session.
    Validates plan selection and organization context.
    """
    plan_id = serializers.UUIDField(required=True)
    success_url = serializers.URLField(required=True)
    cancel_url = serializers.URLField(required=True)
    trial_days = serializers.IntegerField(
        required=False,
        min_value=0,
        max_value=365,
        help_text="Number of days for trial period"
    )

    def validate_success_url(self, value):
        """Validate success_url against allowed domains"""
        from urllib.parse import urlparse
        from django.conf import settings

        parsed = urlparse(value)
        allowed_domains = getattr(settings, 'ALLOWED_REDIRECT_DOMAINS', [])

        # If no allowed domains configured, only allow same-origin (relative URLs)
        if not allowed_domains:
            if parsed.netloc:
                raise serializers.ValidationError(
                    "Only relative URLs are allowed. Configure ALLOWED_REDIRECT_DOMAINS in settings to allow external redirects."
                )
        else:
            # Check if domain is in allowed list
            if parsed.netloc and parsed.netloc not in allowed_domains:
                raise serializers.ValidationError(
                    f"Domain '{parsed.netloc}' is not in the list of allowed redirect domains."
                )

        return value

    def validate_cancel_url(self, value):
        """Validate cancel_url against allowed domains"""
        from urllib.parse import urlparse
        from django.conf import settings

        parsed = urlparse(value)
        allowed_domains = getattr(settings, 'ALLOWED_REDIRECT_DOMAINS', [])

        # If no allowed domains configured, only allow same-origin (relative URLs)
        if not allowed_domains:
            if parsed.netloc:
                raise serializers.ValidationError(
                    "Only relative URLs are allowed. Configure ALLOWED_REDIRECT_DOMAINS in settings to allow external redirects."
                )
        else:
            # Check if domain is in allowed list
            if parsed.netloc and parsed.netloc not in allowed_domains:
                raise serializers.ValidationError(
                    f"Domain '{parsed.netloc}' is not in the list of allowed redirect domains."
                )

        return value

    def validate_plan_id(self, value):
        """Validate that plan exists and is active"""
        try:
            plan = Plan.objects.get(id=value, is_active=True)
        except Plan.DoesNotExist:
            raise serializers.ValidationError("Plan not found or is not active")
        return value

    def validate(self, attrs):
        """Additional validation for checkout session"""
        request = self.context.get('request')
        if not request or not request.user:
            raise serializers.ValidationError("User must be authenticated")

        # Get the organization from context (set in the view)
        organization = self.context.get('organization')
        if not organization:
            raise serializers.ValidationError("Organization context is required")

        # Check if organization already has an active subscription
        active_subscription = Subscription.objects.filter(
            organization=organization,
            status__in=['active', 'trialing']
        ).first()

        if active_subscription:
            raise serializers.ValidationError(
                "Organization already has an active subscription"
            )

        attrs['organization'] = organization
        return attrs


class CancelSubscriptionSerializer(serializers.Serializer):
    """
    Serializer for cancelling a subscription.
    Allows specifying whether to cancel immediately or at period end.
    """
    cancel_at_period_end = serializers.BooleanField(
        default=True,
        help_text="If true, subscription will continue until end of billing period"
    )
    reason = serializers.CharField(
        required=False,
        max_length=500,
        help_text="Optional reason for cancellation"
    )
