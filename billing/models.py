import uuid
from django.db import models
from django.utils.text import slugify
from organizations.models import Organization


class Plan(models.Model):
    """
    Represents a billing plan/tier that customers can subscribe to.
    Each plan has a specific price, billing interval, and set of features.
    """
    BILLING_INTERVAL_CHOICES = [
        ('month', 'Monthly'),
        ('year', 'Yearly'),
    ]

    GATEWAY_CHOICES = [
        ('stripe', 'Stripe'),
        ('razorpay', 'Razorpay'),
        ('paddle', 'Paddle'),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for the plan"
    )
    name = models.CharField(
        max_length=255,
        help_text="Display name of the plan (e.g., 'Pro', 'Enterprise')"
    )
    slug = models.SlugField(
        max_length=255,
        unique=True,
        help_text="URL-friendly identifier for the plan"
    )
    gateway = models.CharField(
        max_length=50,
        choices=GATEWAY_CHOICES,
        help_text="Payment gateway provider for this plan"
    )
    gateway_product_id = models.CharField(
        max_length=255,
        help_text="Product ID from the payment gateway"
    )
    gateway_price_id = models.CharField(
        max_length=255,
        help_text="Price ID from the payment gateway"
    )
    price_cents = models.IntegerField(
        help_text="Price in cents (e.g., 1999 for $19.99)"
    )
    billing_interval = models.CharField(
        max_length=20,
        choices=BILLING_INTERVAL_CHOICES,
        default='month',
        help_text="How often the customer is billed"
    )
    features = models.JSONField(
        default=dict,
        blank=True,
        help_text="Feature flags and limits for this plan"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this plan is currently available for new subscriptions"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['price_cents']
        verbose_name = 'Plan'
        verbose_name_plural = 'Plans'
        indexes = [
            models.Index(fields=['gateway', 'is_active']),
            models.Index(fields=['slug']),
        ]

    def __str__(self):
        return f"{self.name} - {self.get_billing_interval_display()}"

    def save(self, *args, **kwargs):
        """Auto-generate slug from name if not provided"""
        if not self.slug:
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 1

            # Ensure slug is unique
            while Plan.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1

            self.slug = slug

        super().save(*args, **kwargs)

    @property
    def price_display(self):
        """Returns formatted price (e.g., '$19.99')"""
        return f"${self.price_cents / 100:.2f}"


class Subscription(models.Model):
    """
    Represents an organization's active or past subscription to a billing plan.
    Tracks subscription status, billing cycle, and payment gateway details.
    """
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('cancelled', 'Cancelled'),
        ('past_due', 'Past Due'),
        ('trialing', 'Trialing'),
        ('incomplete', 'Incomplete'),
        ('incomplete_expired', 'Incomplete Expired'),
        ('unpaid', 'Unpaid'),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for the subscription"
    )
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='subscriptions',
        help_text="Organization that owns this subscription"
    )
    plan = models.ForeignKey(
        Plan,
        on_delete=models.PROTECT,
        related_name='subscriptions',
        help_text="The plan this subscription is for"
    )
    gateway = models.CharField(
        max_length=50,
        help_text="Payment gateway provider"
    )
    gateway_subscription_id = models.CharField(
        max_length=255,
        unique=True,
        help_text="Subscription ID from the payment gateway"
    )
    gateway_customer_id = models.CharField(
        max_length=255,
        help_text="Customer ID from the payment gateway"
    )
    status = models.CharField(
        max_length=50,
        choices=STATUS_CHOICES,
        default='incomplete',
        help_text="Current status of the subscription"
    )
    current_period_start = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Start of the current billing period"
    )
    current_period_end = models.DateTimeField(
        null=True,
        blank=True,
        help_text="End of the current billing period"
    )
    trial_end = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the trial period ends"
    )
    cancel_at_period_end = models.BooleanField(
        default=False,
        help_text="Whether the subscription will cancel at the end of the current period"
    )
    cancelled_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the subscription was cancelled"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Subscription'
        verbose_name_plural = 'Subscriptions'
        indexes = [
            models.Index(fields=['organization', 'status']),
            models.Index(fields=['gateway_subscription_id']),
            models.Index(fields=['status', 'current_period_end']),
        ]

    def __str__(self):
        return f"{self.organization.name} - {self.plan.name} ({self.status})"

    def is_active(self):
        """Check if subscription is currently active"""
        return self.status in ['active', 'trialing']

    def is_trialing(self):
        """Check if subscription is in trial period"""
        return self.status == 'trialing'


class Invoice(models.Model):
    """
    Represents a billing invoice for a subscription.
    Tracks payment status and links to the payment gateway.
    """
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('open', 'Open'),
        ('paid', 'Paid'),
        ('void', 'Void'),
        ('uncollectible', 'Uncollectible'),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for the invoice"
    )
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='invoices',
        help_text="Organization this invoice belongs to"
    )
    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='invoices',
        help_text="Subscription this invoice is for (if applicable)"
    )
    gateway = models.CharField(
        max_length=50,
        help_text="Payment gateway provider"
    )
    gateway_invoice_id = models.CharField(
        max_length=255,
        unique=True,
        help_text="Invoice ID from the payment gateway"
    )
    amount_cents = models.IntegerField(
        help_text="Total amount in cents"
    )
    currency = models.CharField(
        max_length=3,
        default='USD',
        help_text="Currency code (ISO 4217)"
    )
    status = models.CharField(
        max_length=50,
        choices=STATUS_CHOICES,
        default='draft',
        help_text="Current status of the invoice"
    )
    issued_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the invoice was issued"
    )
    paid_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the invoice was paid"
    )
    invoice_url = models.URLField(
        max_length=500,
        null=True,
        blank=True,
        help_text="URL to view/download the invoice"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Invoice'
        verbose_name_plural = 'Invoices'
        indexes = [
            models.Index(fields=['organization', 'status']),
            models.Index(fields=['gateway_invoice_id']),
            models.Index(fields=['status', 'issued_at']),
        ]

    def __str__(self):
        return f"Invoice {self.gateway_invoice_id} - {self.organization.name}"

    @property
    def amount_display(self):
        """Returns formatted amount (e.g., '$19.99 USD')"""
        return f"${self.amount_cents / 100:.2f} {self.currency}"

    def is_paid(self):
        """Check if invoice has been paid"""
        return self.status == 'paid'


class PaymentMethod(models.Model):
    """
    Represents a payment method (credit card, bank account, etc.) attached to an organization.
    Used for subscription payments and stored in the payment gateway.
    """
    TYPE_CHOICES = [
        ('card', 'Card'),
        ('bank_account', 'Bank Account'),
        ('upi', 'UPI'),
        ('wallet', 'Wallet'),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for the payment method"
    )
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='payment_methods',
        help_text="Organization that owns this payment method"
    )
    gateway = models.CharField(
        max_length=50,
        help_text="Payment gateway provider"
    )
    gateway_payment_method_id = models.CharField(
        max_length=255,
        unique=True,
        help_text="Payment method ID from the gateway"
    )
    type = models.CharField(
        max_length=50,
        choices=TYPE_CHOICES,
        help_text="Type of payment method"
    )
    last4 = models.CharField(
        max_length=4,
        null=True,
        blank=True,
        help_text="Last 4 digits of card/account number"
    )
    brand = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        help_text="Card brand (Visa, Mastercard, etc.) or bank name"
    )
    is_default = models.BooleanField(
        default=False,
        help_text="Whether this is the default payment method"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_default', '-created_at']
        verbose_name = 'Payment Method'
        verbose_name_plural = 'Payment Methods'
        indexes = [
            models.Index(fields=['organization', 'is_default']),
            models.Index(fields=['gateway_payment_method_id']),
        ]

    def __str__(self):
        if self.last4:
            return f"{self.brand or self.type} ending in {self.last4}"
        return f"{self.type} - {self.organization.name}"

    def save(self, *args, **kwargs):
        """Ensure only one default payment method per organization"""
        if self.is_default:
            # Set all other payment methods for this org to non-default
            PaymentMethod.objects.filter(
                organization=self.organization,
                is_default=True
            ).exclude(id=self.id).update(is_default=False)
        super().save(*args, **kwargs)
