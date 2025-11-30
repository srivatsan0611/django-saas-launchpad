"""
Test cases for billing models.

Tests for:
- Plan model (creation, slug generation, price formatting)
- Subscription model (status tracking, period management)
- Invoice model (payment status, amount formatting)
- PaymentMethod model (default management)
"""

from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

from billing.models import Plan, Subscription, Invoice, PaymentMethod
from organizations.models import Organization
from accounts.models import User


class PlanModelTest(TestCase):
    """Test cases for Plan model"""

    def setUp(self):
        """Set up test data"""
        self.plan_data = {
            'name': 'Pro Plan',
            'gateway': 'razorpay',
            'gateway_product_id': 'prod_test123',
            'gateway_price_id': 'price_test123',
            'price_cents': 1999,
            'billing_interval': 'month',
            'features': {'max_users': 10, 'api_access': True},
            'is_active': True,
        }

    def test_plan_creation(self):
        """Test creating a plan"""
        plan = Plan.objects.create(**self.plan_data)

        self.assertEqual(plan.name, 'Pro Plan')
        self.assertEqual(plan.price_cents, 1999)
        self.assertEqual(plan.billing_interval, 'month')
        self.assertTrue(plan.is_active)

    def test_plan_slug_auto_generation(self):
        """Test that slug is auto-generated from name"""
        plan = Plan.objects.create(**self.plan_data)

        self.assertEqual(plan.slug, 'pro-plan')

    def test_plan_slug_uniqueness(self):
        """Test that duplicate plan names get unique slugs"""
        plan1 = Plan.objects.create(**self.plan_data)
        plan2 = Plan.objects.create(**self.plan_data)

        self.assertEqual(plan1.slug, 'pro-plan')
        self.assertEqual(plan2.slug, 'pro-plan-1')

    def test_price_display_property(self):
        """Test price_display property formatting"""
        plan = Plan.objects.create(**self.plan_data)

        self.assertEqual(plan.price_display, '$19.99')

    def test_plan_string_representation(self):
        """Test __str__ method"""
        plan = Plan.objects.create(**self.plan_data)

        self.assertIn('Pro Plan', str(plan))
        self.assertIn('Monthly', str(plan))


class SubscriptionModelTest(TestCase):
    """Test cases for Subscription model"""

    def setUp(self):
        """Set up test data"""
        # Create user and organization
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        self.organization = Organization.objects.create(
            name='Test Org',
            owner=self.user
        )

        # Create plan
        self.plan = Plan.objects.create(
            name='Pro Plan',
            gateway='razorpay',
            gateway_product_id='prod_test123',
            gateway_price_id='price_test123',
            price_cents=1999,
            billing_interval='month',
        )

    def test_subscription_creation(self):
        """Test creating a subscription"""
        subscription = Subscription.objects.create(
            organization=self.organization,
            plan=self.plan,
            gateway='razorpay',
            gateway_subscription_id='sub_test123',
            gateway_customer_id='cus_test123',
            status='active',
        )

        self.assertEqual(subscription.organization, self.organization)
        self.assertEqual(subscription.plan, self.plan)
        self.assertEqual(subscription.status, 'active')

    def test_is_active_method(self):
        """Test is_active() method"""
        # Active subscription
        active_sub = Subscription.objects.create(
            organization=self.organization,
            plan=self.plan,
            gateway='razorpay',
            gateway_subscription_id='sub_active',
            gateway_customer_id='cus_test123',
            status='active',
        )
        self.assertTrue(active_sub.is_active())

        # Trialing subscription
        trial_sub = Subscription.objects.create(
            organization=self.organization,
            plan=self.plan,
            gateway='razorpay',
            gateway_subscription_id='sub_trial',
            gateway_customer_id='cus_test123',
            status='trialing',
        )
        self.assertTrue(trial_sub.is_active())

        # Cancelled subscription
        cancelled_sub = Subscription.objects.create(
            organization=self.organization,
            plan=self.plan,
            gateway='razorpay',
            gateway_subscription_id='sub_cancelled',
            gateway_customer_id='cus_test123',
            status='cancelled',
        )
        self.assertFalse(cancelled_sub.is_active())

    def test_is_trialing_method(self):
        """Test is_trialing() method"""
        subscription = Subscription.objects.create(
            organization=self.organization,
            plan=self.plan,
            gateway='razorpay',
            gateway_subscription_id='sub_test123',
            gateway_customer_id='cus_test123',
            status='trialing',
        )

        self.assertTrue(subscription.is_trialing())


class InvoiceModelTest(TestCase):
    """Test cases for Invoice model"""

    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        self.organization = Organization.objects.create(
            name='Test Org',
            owner=self.user
        )

    def test_invoice_creation(self):
        """Test creating an invoice"""
        invoice = Invoice.objects.create(
            organization=self.organization,
            gateway='razorpay',
            gateway_invoice_id='inv_test123',
            amount_cents=1999,
            currency='USD',
            status='paid',
        )

        self.assertEqual(invoice.organization, self.organization)
        self.assertEqual(invoice.amount_cents, 1999)
        self.assertEqual(invoice.status, 'paid')

    def test_amount_display_property(self):
        """Test amount_display property formatting"""
        invoice = Invoice.objects.create(
            organization=self.organization,
            gateway='razorpay',
            gateway_invoice_id='inv_test123',
            amount_cents=1999,
            currency='USD',
            status='paid',
        )

        self.assertEqual(invoice.amount_display, '$19.99 USD')

    def test_is_paid_method(self):
        """Test is_paid() method"""
        # Paid invoice
        paid_invoice = Invoice.objects.create(
            organization=self.organization,
            gateway='razorpay',
            gateway_invoice_id='inv_paid',
            amount_cents=1999,
            currency='USD',
            status='paid',
        )
        self.assertTrue(paid_invoice.is_paid())

        # Unpaid invoice
        unpaid_invoice = Invoice.objects.create(
            organization=self.organization,
            gateway='razorpay',
            gateway_invoice_id='inv_unpaid',
            amount_cents=1999,
            currency='USD',
            status='open',
        )
        self.assertFalse(unpaid_invoice.is_paid())


class PaymentMethodModelTest(TestCase):
    """Test cases for PaymentMethod model"""

    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        self.organization = Organization.objects.create(
            name='Test Org',
            owner=self.user
        )

    def test_payment_method_creation(self):
        """Test creating a payment method"""
        payment_method = PaymentMethod.objects.create(
            organization=self.organization,
            gateway='razorpay',
            gateway_payment_method_id='pm_test123',
            type='card',
            last4='4242',
            brand='Visa',
            is_default=True,
        )

        self.assertEqual(payment_method.organization, self.organization)
        self.assertEqual(payment_method.type, 'card')
        self.assertTrue(payment_method.is_default)

    def test_default_payment_method_uniqueness(self):
        """Test that only one payment method can be default per organization"""
        # Create first default payment method
        pm1 = PaymentMethod.objects.create(
            organization=self.organization,
            gateway='razorpay',
            gateway_payment_method_id='pm_test1',
            type='card',
            is_default=True,
        )
        self.assertTrue(pm1.is_default)

        # Create second default payment method
        pm2 = PaymentMethod.objects.create(
            organization=self.organization,
            gateway='razorpay',
            gateway_payment_method_id='pm_test2',
            type='card',
            is_default=True,
        )

        # Refresh first payment method from database
        pm1.refresh_from_db()

        # First should no longer be default
        self.assertFalse(pm1.is_default)
        # Second should be default
        self.assertTrue(pm2.is_default)

    def test_payment_method_string_representation(self):
        """Test __str__ method"""
        payment_method = PaymentMethod.objects.create(
            organization=self.organization,
            gateway='razorpay',
            gateway_payment_method_id='pm_test123',
            type='card',
            last4='4242',
            brand='Visa',
        )

        self.assertIn('Visa', str(payment_method))
        self.assertIn('4242', str(payment_method))
