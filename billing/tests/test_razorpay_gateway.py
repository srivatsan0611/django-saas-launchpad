"""
Tests for Razorpay payment gateway implementation.

All tests use mocked Razorpay API calls to ensure:
- Fast test execution
- No dependency on external API
- Consistent test results
"""

import pytest
import hmac
import hashlib
import json
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

from billing.gateways.razorpay_gateway import RazorpayGateway
from billing.gateways.base import GatewayResponse, GatewayException


@pytest.fixture
def mock_razorpay_client():
    """Fixture for mocked Razorpay client"""
    with patch('billing.gateways.razorpay_gateway.razorpay.Client') as mock_client:
        yield mock_client


@pytest.fixture
def razorpay_gateway(mock_razorpay_client):
    """Fixture for Razorpay gateway instance with mocked client"""
    return RazorpayGateway(
        api_key='rzp_test_dummy_key',
        api_secret='dummy_secret',
        webhook_secret='whsec_test_secret'
    )


class TestCustomerManagement:
    """Tests for customer-related operations"""

    def test_create_customer_success(self, razorpay_gateway, mock_razorpay_client):
        """Test successful customer creation"""
        # Mock response
        mock_customer = {
            'id': 'cust_test123',
            'email': 'test@example.com',
            'name': 'Test User',
            'created_at': 1234567890
        }

        mock_razorpay_client.return_value.customer.create.return_value = mock_customer

        # Execute
        response = razorpay_gateway.create_customer(
            email='test@example.com',
            name='Test User'
        )

        # Assert
        assert response.success is True
        assert response.data['customer_id'] == 'cust_test123'
        assert response.data['email'] == 'test@example.com'
        assert response.data['name'] == 'Test User'
        assert response.gateway_response == mock_customer

    def test_create_customer_with_metadata(self, razorpay_gateway, mock_razorpay_client):
        """Test customer creation with metadata"""
        mock_customer = {
            'id': 'cust_test123',
            'email': 'test@example.com',
            'name': 'Test User',
            'created_at': 1234567890,
            'notes': {'org_id': 'org_123', 'plan': 'pro'}
        }

        mock_razorpay_client.return_value.customer.create.return_value = mock_customer

        response = razorpay_gateway.create_customer(
            email='test@example.com',
            name='Test User',
            metadata={'org_id': 'org_123', 'plan': 'pro'}
        )

        assert response.success is True
        assert response.data['customer_id'] == 'cust_test123'

    def test_create_customer_api_error(self, razorpay_gateway, mock_razorpay_client):
        """Test customer creation with API error"""
        import razorpay

        mock_razorpay_client.return_value.customer.create.side_effect = \
            razorpay.errors.BadRequestError('Invalid email')

        with pytest.raises(GatewayException) as exc_info:
            razorpay_gateway.create_customer(email='invalid-email')

        assert 'Failed to create customer' in str(exc_info.value)
        assert exc_info.value.error_code == 'customer_creation_failed'

    def test_get_customer_success(self, razorpay_gateway, mock_razorpay_client):
        """Test retrieving customer details"""
        mock_customer = {
            'id': 'cust_test123',
            'email': 'test@example.com',
            'name': 'Test User',
            'created_at': 1234567890
        }

        mock_razorpay_client.return_value.customer.fetch.return_value = mock_customer

        response = razorpay_gateway.get_customer('cust_test123')

        assert response.success is True
        assert response.data['customer_id'] == 'cust_test123'
        assert response.data['email'] == 'test@example.com'

    def test_get_customer_not_found(self, razorpay_gateway, mock_razorpay_client):
        """Test retrieving non-existent customer"""
        import razorpay

        mock_razorpay_client.return_value.customer.fetch.side_effect = \
            razorpay.errors.BadRequestError('Customer not found')

        with pytest.raises(GatewayException) as exc_info:
            razorpay_gateway.get_customer('cust_invalid')

        assert 'Customer not found' in str(exc_info.value)
        assert exc_info.value.error_code == 'customer_not_found'


class TestSubscriptionManagement:
    """Tests for subscription-related operations"""

    def test_create_subscription_success(self, razorpay_gateway, mock_razorpay_client):
        """Test successful subscription creation"""
        mock_subscription = {
            'id': 'sub_test123',
            'status': 'created',
            'plan_id': 'plan_test123',
            'customer_id': 'cust_test123',
            'current_start': 1234567890,
            'current_end': 1237159890,
            'charge_at': 1234567890
        }

        mock_razorpay_client.return_value.subscription.create.return_value = mock_subscription

        response = razorpay_gateway.create_subscription(
            customer_id='cust_test123',
            plan_id='plan_test123'
        )

        assert response.success is True
        assert response.data['subscription_id'] == 'sub_test123'
        assert response.data['status'] == 'created'
        assert response.data['plan_id'] == 'plan_test123'

    def test_create_subscription_with_trial(self, razorpay_gateway, mock_razorpay_client):
        """Test subscription creation with trial period"""
        mock_subscription = {
            'id': 'sub_test123',
            'status': 'created',
            'plan_id': 'plan_test123',
            'customer_id': 'cust_test123',
            'start_at': int((datetime.now() + timedelta(days=7)).timestamp())
        }

        mock_razorpay_client.return_value.subscription.create.return_value = mock_subscription

        response = razorpay_gateway.create_subscription(
            customer_id='cust_test123',
            plan_id='plan_test123',
            trial_days=7
        )

        assert response.success is True
        assert 'start_at' in response.data

    def test_create_subscription_with_metadata(self, razorpay_gateway, mock_razorpay_client):
        """Test subscription creation with metadata"""
        mock_subscription = {
            'id': 'sub_test123',
            'status': 'created',
            'plan_id': 'plan_test123',
            'customer_id': 'cust_test123',
            'notes': {'org_id': 'org_123'}
        }

        mock_razorpay_client.return_value.subscription.create.return_value = mock_subscription

        response = razorpay_gateway.create_subscription(
            customer_id='cust_test123',
            plan_id='plan_test123',
            metadata={'org_id': 'org_123'}
        )

        assert response.success is True

    def test_create_subscription_api_error(self, razorpay_gateway, mock_razorpay_client):
        """Test subscription creation with API error"""
        import razorpay

        mock_razorpay_client.return_value.subscription.create.side_effect = \
            razorpay.errors.BadRequestError('Invalid plan')

        with pytest.raises(GatewayException) as exc_info:
            razorpay_gateway.create_subscription(
                customer_id='cust_test123',
                plan_id='invalid_plan'
            )

        assert 'Failed to create subscription' in str(exc_info.value)
        assert exc_info.value.error_code == 'subscription_creation_failed'

    def test_cancel_subscription_at_period_end(self, razorpay_gateway, mock_razorpay_client):
        """Test cancelling subscription at period end"""
        mock_subscription = {
            'id': 'sub_test123',
            'status': 'cancelled',
            'ended_at': int(datetime.now().timestamp()),
            'cancelled_at': int(datetime.now().timestamp())
        }

        mock_razorpay_client.return_value.subscription.cancel.return_value = mock_subscription

        response = razorpay_gateway.cancel_subscription(
            subscription_id='sub_test123',
            cancel_at_period_end=True
        )

        assert response.success is True
        assert response.data['subscription_id'] == 'sub_test123'
        assert response.data['status'] == 'cancelled'

    def test_cancel_subscription_immediately(self, razorpay_gateway, mock_razorpay_client):
        """Test cancelling subscription immediately"""
        mock_subscription = {
            'id': 'sub_test123',
            'status': 'cancelled',
            'ended_at': int(datetime.now().timestamp()),
            'cancelled_at': int(datetime.now().timestamp())
        }

        mock_razorpay_client.return_value.subscription.cancel.return_value = mock_subscription

        response = razorpay_gateway.cancel_subscription(
            subscription_id='sub_test123',
            cancel_at_period_end=False
        )

        assert response.success is True
        assert response.data['status'] == 'cancelled'

    def test_cancel_subscription_api_error(self, razorpay_gateway, mock_razorpay_client):
        """Test subscription cancellation with API error"""
        import razorpay

        mock_razorpay_client.return_value.subscription.cancel.side_effect = \
            razorpay.errors.BadRequestError('Subscription not found')

        with pytest.raises(GatewayException) as exc_info:
            razorpay_gateway.cancel_subscription('sub_invalid')

        assert 'Failed to cancel subscription' in str(exc_info.value)

    def test_get_subscription_success(self, razorpay_gateway, mock_razorpay_client):
        """Test retrieving subscription details"""
        mock_subscription = {
            'id': 'sub_test123',
            'status': 'active',
            'plan_id': 'plan_test123',
            'customer_id': 'cust_test123',
            'current_start': 1234567890,
            'current_end': 1237159890
        }

        mock_razorpay_client.return_value.subscription.fetch.return_value = mock_subscription

        response = razorpay_gateway.get_subscription('sub_test123')

        assert response.success is True
        assert response.data['subscription_id'] == 'sub_test123'
        assert response.data['status'] == 'active'

    def test_get_subscription_not_found(self, razorpay_gateway, mock_razorpay_client):
        """Test retrieving non-existent subscription"""
        import razorpay

        mock_razorpay_client.return_value.subscription.fetch.side_effect = \
            razorpay.errors.BadRequestError('Subscription not found')

        with pytest.raises(GatewayException) as exc_info:
            razorpay_gateway.get_subscription('sub_invalid')

        assert 'Subscription not found' in str(exc_info.value)


class TestProductAndPricing:
    """Tests for product and pricing operations"""

    def test_create_product(self, razorpay_gateway):
        """Test product creation (mock operation in Razorpay)"""
        response = razorpay_gateway.create_product(
            name='Pro Plan',
            description='Professional plan with all features'
        )

        assert response.success is True
        assert response.data['product_id'] == 'pro_plan'
        assert response.data['name'] == 'Pro Plan'

    def test_create_price_monthly(self, razorpay_gateway, mock_razorpay_client):
        """Test creating monthly plan"""
        mock_plan = {
            'id': 'plan_test123',
            'period': 'monthly',
            'interval': 1,
            'item': {
                'name': 'Pro Plan',
                'amount': 99900,
                'currency': 'INR'
            }
        }

        mock_razorpay_client.return_value.plan.create.return_value = mock_plan

        response = razorpay_gateway.create_price(
            product_id='pro_plan',
            amount_cents=99900,
            currency='inr',
            interval='month',
            interval_count=1
        )

        assert response.success is True
        assert response.data['plan_id'] == 'plan_test123'
        assert response.data['period'] == 'monthly'
        assert response.data['amount'] == 99900
        assert response.data['currency'] == 'INR'

    def test_create_price_yearly(self, razorpay_gateway, mock_razorpay_client):
        """Test creating yearly plan"""
        mock_plan = {
            'id': 'plan_test456',
            'period': 'yearly',
            'interval': 1,
            'item': {
                'name': 'Pro Plan',
                'amount': 999900,
                'currency': 'INR'
            }
        }

        mock_razorpay_client.return_value.plan.create.return_value = mock_plan

        response = razorpay_gateway.create_price(
            product_id='pro_plan',
            amount_cents=999900,
            currency='inr',
            interval='year',
            interval_count=1
        )

        assert response.success is True
        assert response.data['period'] == 'yearly'

    def test_create_price_api_error(self, razorpay_gateway, mock_razorpay_client):
        """Test plan creation with API error"""
        import razorpay

        mock_razorpay_client.return_value.plan.create.side_effect = \
            razorpay.errors.BadRequestError('Invalid amount')

        with pytest.raises(GatewayException) as exc_info:
            razorpay_gateway.create_price(
                product_id='pro_plan',
                amount_cents=-100,
                currency='inr',
                interval='month'
            )

        assert 'Failed to create plan' in str(exc_info.value)


class TestCheckoutAndInvoices:
    """Tests for checkout and invoice operations"""

    def test_create_checkout_session(self, razorpay_gateway, mock_razorpay_client):
        """Test creating checkout session"""
        mock_subscription = {
            'id': 'sub_test123',
            'status': 'created',
            'plan_id': 'plan_test123',
            'customer_id': 'cust_test123'
        }

        mock_razorpay_client.return_value.subscription.create.return_value = mock_subscription

        response = razorpay_gateway.create_checkout_session(
            customer_id='cust_test123',
            plan_id='plan_test123',
            success_url='https://example.com/success',
            cancel_url='https://example.com/cancel'
        )

        assert response.success is True
        assert 'checkout_url' in response.data
        assert 'subscription_id' in response.data
        assert response.data['subscription_id'] == 'sub_test123'

    def test_get_invoice_success(self, razorpay_gateway, mock_razorpay_client):
        """Test retrieving invoice details"""
        mock_invoice = {
            'id': 'inv_test123',
            'amount': 99900,
            'currency': 'INR',
            'status': 'paid',
            'customer_id': 'cust_test123',
            'subscription_id': 'sub_test123',
            'created_at': 1234567890,
            'paid_at': 1234567900
        }

        mock_razorpay_client.return_value.invoice.fetch.return_value = mock_invoice

        response = razorpay_gateway.get_invoice('inv_test123')

        assert response.success is True
        assert response.data['invoice_id'] == 'inv_test123'
        assert response.data['amount'] == 99900
        assert response.data['status'] == 'paid'

    def test_get_invoice_not_found(self, razorpay_gateway, mock_razorpay_client):
        """Test retrieving non-existent invoice"""
        import razorpay

        mock_razorpay_client.return_value.invoice.fetch.side_effect = \
            razorpay.errors.BadRequestError('Invoice not found')

        with pytest.raises(GatewayException) as exc_info:
            razorpay_gateway.get_invoice('inv_invalid')

        assert 'Invoice not found' in str(exc_info.value)


class TestWebhooks:
    """Tests for webhook verification and parsing"""

    def test_verify_webhook_signature_valid(self, razorpay_gateway):
        """Test webhook signature verification with valid signature"""
        payload = b'{"event": "subscription.charged", "payload": {}}'

        # Generate valid signature
        signature = hmac.new(
            key='whsec_test_secret'.encode('utf-8'),
            msg=payload,
            digestmod=hashlib.sha256
        ).hexdigest()

        result = razorpay_gateway.verify_webhook_signature(payload, signature)

        assert result is True

    def test_verify_webhook_signature_invalid(self, razorpay_gateway):
        """Test webhook signature verification with invalid signature"""
        payload = b'{"event": "subscription.charged", "payload": {}}'
        invalid_signature = 'invalid_signature_12345'

        result = razorpay_gateway.verify_webhook_signature(payload, invalid_signature)

        assert result is False

    def test_verify_webhook_signature_no_secret(self):
        """Test webhook verification without webhook secret"""
        gateway = RazorpayGateway(
            api_key='rzp_test_key',
            api_secret='secret',
            webhook_secret=None
        )

        with pytest.raises(GatewayException) as exc_info:
            gateway.verify_webhook_signature(b'payload', 'signature')

        assert 'Webhook secret not configured' in str(exc_info.value)

    def test_parse_webhook_event_subscription_charged(self, razorpay_gateway):
        """Test parsing subscription.charged webhook event"""
        payload = {
            'event': 'subscription.charged',
            'payload': {
                'subscription': {
                    'entity': {
                        'id': 'sub_test123',
                        'status': 'active',
                        'plan_id': 'plan_test123'
                    }
                },
                'payment': {
                    'entity': {
                        'id': 'pay_test123',
                        'amount': 99900,
                        'status': 'captured'
                    }
                }
            }
        }

        parsed = razorpay_gateway.parse_webhook_event(payload)

        assert parsed['event_type'] == 'subscription.charged'
        assert parsed['event_id'] == 'sub_test123'
        assert 'subscription' in parsed['data']
        assert 'payment' in parsed['data']
        assert parsed['data']['subscription']['id'] == 'sub_test123'

    def test_parse_webhook_event_payment_failed(self, razorpay_gateway):
        """Test parsing payment.failed webhook event"""
        payload = {
            'event': 'payment.failed',
            'payload': {
                'payment': {
                    'entity': {
                        'id': 'pay_test456',
                        'amount': 99900,
                        'status': 'failed',
                        'error_code': 'GATEWAY_ERROR'
                    }
                },
                'subscription': {
                    'entity': {}
                }
            }
        }

        parsed = razorpay_gateway.parse_webhook_event(payload)

        assert parsed['event_type'] == 'payment.failed'
        assert parsed['event_id'] == 'pay_test456'
        assert parsed['data']['payment']['status'] == 'failed'

    def test_parse_webhook_event_invalid_payload(self, razorpay_gateway):
        """Test parsing invalid webhook payload"""
        invalid_payload = {}  # Missing 'event' and 'payload' keys

        parsed = razorpay_gateway.parse_webhook_event(invalid_payload)

        # Should return with None values instead of raising exception
        assert parsed['event_type'] is None
        assert parsed['event_id'] is None


class TestErrorHandling:
    """Tests for error handling and edge cases"""

    def test_gateway_exception_with_all_params(self):
        """Test GatewayException with all parameters"""
        exception = GatewayException(
            message='Test error',
            error_code='test_code',
            gateway_response={'error': 'details'}
        )

        assert exception.message == 'Test error'
        assert exception.error_code == 'test_code'
        assert exception.gateway_response == {'error': 'details'}
        assert str(exception) == 'Test error'

    def test_gateway_response_structure(self):
        """Test GatewayResponse dataclass structure"""
        response = GatewayResponse(
            success=True,
            data={'key': 'value'},
            error_message=None,
            error_code=None,
            gateway_response={'raw': 'data'}
        )

        assert response.success is True
        assert response.data == {'key': 'value'}
        assert response.error_message is None
        assert response.gateway_response == {'raw': 'data'}

    def test_gateway_response_with_error(self):
        """Test GatewayResponse with error information"""
        response = GatewayResponse(
            success=False,
            data={},
            error_message='Payment failed',
            error_code='PAYMENT_ERROR'
        )

        assert response.success is False
        assert response.error_message == 'Payment failed'
        assert response.error_code == 'PAYMENT_ERROR'

    def test_gateway_response_with_status_code(self):
        """Test GatewayResponse includes HTTP status codes"""
        # Success response
        success_response = GatewayResponse(
            success=True,
            data={'customer_id': 'cust_123'},
            status_code=200
        )

        assert success_response.success is True
        assert success_response.status_code == 200

        # Created response
        created_response = GatewayResponse(
            success=True,
            data={'subscription_id': 'sub_123'},
            status_code=201
        )

        assert created_response.status_code == 201

        # Error response
        error_response = GatewayResponse(
            success=False,
            data={},
            status_code=400,
            error_message='Bad request'
        )

        assert error_response.status_code == 400
        assert error_response.success is False
