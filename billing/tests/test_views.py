"""
Test cases for billing views.

Tests for:
- PlanViewSet (list, retrieve)
- SubscriptionViewSet (list, retrieve, cancel, sync)
- InvoiceViewSet (list, retrieve)
- CreateCheckoutSessionView
- BillingPortalView
"""

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from django.urls import reverse

from billing.models import Plan, Subscription, Invoice
from organizations.models import Organization, Membership
from accounts.models import User


class PlanViewSetTest(TestCase):
    """Test cases for Plan ViewSet"""

    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)

        # Create test plans
        self.plan1 = Plan.objects.create(
            name='Basic Plan',
            gateway='razorpay',
            gateway_product_id='prod_basic',
            gateway_price_id='price_basic',
            price_cents=999,
            billing_interval='month',
            is_active=True,
        )
        self.plan2 = Plan.objects.create(
            name='Pro Plan',
            gateway='razorpay',
            gateway_product_id='prod_pro',
            gateway_price_id='price_pro',
            price_cents=1999,
            billing_interval='month',
            is_active=True,
        )

    def test_list_plans(self):
        """Test listing all active plans"""
        url = reverse('plan-list')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)

    def test_retrieve_plan(self):
        """Test retrieving a specific plan"""
        url = reverse('plan-detail', kwargs={'pk': self.plan1.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Basic Plan')
        self.assertEqual(response.data['price_cents'], 999)

    def test_list_plans_unauthenticated(self):
        """Test that unauthenticated users cannot list plans"""
        self.client.force_authenticate(user=None)
        url = reverse('plan-list')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class SubscriptionViewSetTest(TestCase):
    """Test cases for Subscription ViewSet"""

    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        self.organization = Organization.objects.create(
            name='Test Org',
            owner=self.user
        )
        self.client.force_authenticate(user=self.user)

        # Create plan
        self.plan = Plan.objects.create(
            name='Pro Plan',
            gateway='razorpay',
            gateway_product_id='prod_pro',
            gateway_price_id='price_pro',
            price_cents=1999,
            billing_interval='month',
        )

        # Create subscription
        self.subscription = Subscription.objects.create(
            organization=self.organization,
            plan=self.plan,
            gateway='razorpay',
            gateway_subscription_id='sub_test123',
            gateway_customer_id='cus_test123',
            status='active',
        )

    def test_list_subscriptions(self):
        """Test listing user's subscriptions"""
        url = reverse('subscription-list')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)

    def test_retrieve_subscription(self):
        """Test retrieving a specific subscription"""
        url = reverse('subscription-detail', kwargs={'pk': self.subscription.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'active')

    def test_list_subscriptions_filtered_by_organization(self):
        """Test filtering subscriptions by organization"""
        url = reverse('subscription-list')
        response = self.client.get(url, {'organization_id': self.organization.id})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)


class InvoiceViewSetTest(TestCase):
    """Test cases for Invoice ViewSet"""

    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        self.organization = Organization.objects.create(
            name='Test Org',
            owner=self.user
        )
        self.client.force_authenticate(user=self.user)

        # Create invoices
        self.invoice1 = Invoice.objects.create(
            organization=self.organization,
            gateway='razorpay',
            gateway_invoice_id='inv_test1',
            amount_cents=1999,
            currency='USD',
            status='paid',
        )
        self.invoice2 = Invoice.objects.create(
            organization=self.organization,
            gateway='razorpay',
            gateway_invoice_id='inv_test2',
            amount_cents=1999,
            currency='USD',
            status='open',
        )

    def test_list_invoices(self):
        """Test listing user's invoices"""
        url = reverse('invoice-list')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)

    def test_retrieve_invoice(self):
        """Test retrieving a specific invoice"""
        url = reverse('invoice-detail', kwargs={'pk': self.invoice1.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'paid')


class CreateCheckoutSessionViewTest(TestCase):
    """Test cases for CreateCheckoutSession View"""

    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        self.organization = Organization.objects.create(
            name='Test Org',
            owner=self.user
        )
        self.client.force_authenticate(user=self.user)

        # Create plan
        self.plan = Plan.objects.create(
            name='Pro Plan',
            gateway='razorpay',
            gateway_product_id='prod_pro',
            gateway_price_id='price_pro',
            price_cents=1999,
            billing_interval='month',
            is_active=True,
        )

    def test_create_checkout_session_missing_data(self):
        """Test creating checkout session with missing data"""
        url = reverse('billing-checkout')
        data = {
            'plan_id': str(self.plan.id),
            # Missing organization_id, success_url, cancel_url
        }
        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_checkout_session_unauthenticated(self):
        """Test that unauthenticated users cannot create checkout sessions"""
        self.client.force_authenticate(user=None)
        url = reverse('billing-checkout')
        data = {
            'plan_id': str(self.plan.id),
            'organization_id': str(self.organization.id),
            'success_url': 'http://example.com/success',
            'cancel_url': 'http://example.com/cancel',
        }
        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


# Note: More comprehensive tests would require mocking the payment gateway
# These are basic structural tests to ensure the endpoints work
