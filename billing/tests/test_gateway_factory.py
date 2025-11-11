"""
Tests for payment gateway factory.

Tests cover:
- Gateway selection based on configuration
- Gateway registration
- Error handling for unsupported gateways
- Configuration validation
"""

import pytest
from unittest.mock import patch
from django.conf import settings

from billing.gateways.factory import (
    get_gateway,
    register_gateway,
    list_available_gateways,
    GATEWAY_REGISTRY
)
from billing.gateways.base import BasePaymentGateway, GatewayException
from billing.gateways.razorpay_gateway import RazorpayGateway


class TestGetGateway:
    """Tests for get_gateway function"""

    def test_get_razorpay_gateway_explicit(self):
        """Test getting Razorpay gateway by name"""
        gateway = get_gateway('razorpay')

        assert isinstance(gateway, RazorpayGateway)
        assert gateway.api_key == settings.RAZORPAY_KEY_ID
        assert gateway.api_secret == settings.RAZORPAY_KEY_SECRET

    def test_get_razorpay_gateway_case_insensitive(self):
        """Test gateway name is case-insensitive"""
        gateway1 = get_gateway('RAZORPAY')
        gateway2 = get_gateway('RazorPay')
        gateway3 = get_gateway('razorpay')

        assert all(isinstance(g, RazorpayGateway) for g in [gateway1, gateway2, gateway3])

    def test_get_gateway_with_whitespace(self):
        """Test gateway name handles whitespace"""
        gateway = get_gateway('  razorpay  ')

        assert isinstance(gateway, RazorpayGateway)

    @patch.object(settings, 'DEFAULT_PAYMENT_GATEWAY', 'razorpay')
    def test_get_gateway_uses_default(self):
        """Test getting gateway without specifying name uses default"""
        gateway = get_gateway()

        assert isinstance(gateway, RazorpayGateway)

    def test_get_unsupported_gateway(self):
        """Test error when requesting unsupported gateway"""
        with pytest.raises(GatewayException) as exc_info:
            get_gateway('unsupported_gateway')

        assert 'Unsupported payment gateway' in str(exc_info.value)
        assert exc_info.value.error_code == 'unsupported_gateway'
        assert 'razorpay' in str(exc_info.value).lower()

    @patch.object(settings, 'RAZORPAY_KEY_ID', None)
    def test_get_gateway_missing_config(self):
        """Test error when gateway configuration is missing"""
        # Remove the setting temporarily
        delattr(settings, 'RAZORPAY_KEY_ID')

        with pytest.raises(GatewayException) as exc_info:
            get_gateway('razorpay')

        assert 'Missing configuration' in str(exc_info.value)
        assert exc_info.value.error_code == 'gateway_config_missing'

        # Restore setting for other tests
        settings.RAZORPAY_KEY_ID = 'rzp_test_dummy'

    def test_gateway_includes_webhook_secret(self):
        """Test that webhook secret is passed to gateway"""
        with patch.object(settings, 'RAZORPAY_WEBHOOK_SECRET', 'test_webhook_secret'):
            gateway = get_gateway('razorpay')

            assert gateway.webhook_secret == 'test_webhook_secret'

    def test_gateway_without_webhook_secret(self):
        """Test gateway creation when webhook secret is not configured"""
        # Temporarily remove webhook secret
        original_secret = getattr(settings, 'RAZORPAY_WEBHOOK_SECRET', None)
        if hasattr(settings, 'RAZORPAY_WEBHOOK_SECRET'):
            delattr(settings, 'RAZORPAY_WEBHOOK_SECRET')

        gateway = get_gateway('razorpay')

        assert gateway.webhook_secret is None

        # Restore
        if original_secret:
            settings.RAZORPAY_WEBHOOK_SECRET = original_secret


class TestRegisterGateway:
    """Tests for register_gateway function"""

    def test_register_custom_gateway(self):
        """Test registering a custom gateway"""
        class CustomGateway(BasePaymentGateway):
            def create_customer(self, email, name=None, metadata=None):
                pass

            def get_customer(self, customer_id):
                pass

            def create_subscription(self, customer_id, plan_id, trial_days=None, metadata=None):
                pass

            def cancel_subscription(self, subscription_id, cancel_at_period_end=True):
                pass

            def get_subscription(self, subscription_id):
                pass

            def create_product(self, name, description=None):
                pass

            def create_price(self, product_id, amount_cents, currency, interval, interval_count=1):
                pass

            def create_checkout_session(self, customer_id, plan_id, success_url, cancel_url, metadata=None):
                pass

            def get_invoice(self, invoice_id):
                pass

            def verify_webhook_signature(self, payload, signature):
                pass

            def parse_webhook_event(self, payload):
                pass

        # Register custom gateway
        register_gateway('custom', CustomGateway)

        # Verify it's in registry
        assert 'custom' in GATEWAY_REGISTRY
        assert GATEWAY_REGISTRY['custom'] == CustomGateway

        # Clean up
        del GATEWAY_REGISTRY['custom']

    def test_register_gateway_invalid_class(self):
        """Test registering gateway with invalid class"""
        class NotAGateway:
            pass

        with pytest.raises(GatewayException) as exc_info:
            register_gateway('invalid', NotAGateway)

        assert 'must extend BasePaymentGateway' in str(exc_info.value)
        assert exc_info.value.error_code == 'invalid_gateway_class'

    def test_register_gateway_overwrites_existing(self):
        """Test that registering gateway with existing name overwrites"""
        class NewRazorpayGateway(BasePaymentGateway):
            def create_customer(self, email, name=None, metadata=None):
                pass

            def get_customer(self, customer_id):
                pass

            def create_subscription(self, customer_id, plan_id, trial_days=None, metadata=None):
                pass

            def cancel_subscription(self, subscription_id, cancel_at_period_end=True):
                pass

            def get_subscription(self, subscription_id):
                pass

            def create_product(self, name, description=None):
                pass

            def create_price(self, product_id, amount_cents, currency, interval, interval_count=1):
                pass

            def create_checkout_session(self, customer_id, plan_id, success_url, cancel_url, metadata=None):
                pass

            def get_invoice(self, invoice_id):
                pass

            def verify_webhook_signature(self, payload, signature):
                pass

            def parse_webhook_event(self, payload):
                pass

        original_gateway = GATEWAY_REGISTRY['razorpay']

        # Register with same name
        register_gateway('razorpay', NewRazorpayGateway)

        assert GATEWAY_REGISTRY['razorpay'] == NewRazorpayGateway

        # Restore original
        GATEWAY_REGISTRY['razorpay'] = original_gateway


class TestListAvailableGateways:
    """Tests for list_available_gateways function"""

    def test_list_available_gateways(self):
        """Test listing all available gateways"""
        gateways = list_available_gateways()

        assert isinstance(gateways, list)
        assert 'razorpay' in gateways
        assert len(gateways) >= 1

    def test_list_includes_custom_gateway(self):
        """Test that custom registered gateways appear in list"""
        class TestGateway(BasePaymentGateway):
            def create_customer(self, email, name=None, metadata=None):
                pass

            def get_customer(self, customer_id):
                pass

            def create_subscription(self, customer_id, plan_id, trial_days=None, metadata=None):
                pass

            def cancel_subscription(self, subscription_id, cancel_at_period_end=True):
                pass

            def get_subscription(self, subscription_id):
                pass

            def create_product(self, name, description=None):
                pass

            def create_price(self, product_id, amount_cents, currency, interval, interval_count=1):
                pass

            def create_checkout_session(self, customer_id, plan_id, success_url, cancel_url, metadata=None):
                pass

            def get_invoice(self, invoice_id):
                pass

            def verify_webhook_signature(self, payload, signature):
                pass

            def parse_webhook_event(self, payload):
                pass

        # Register and verify it appears
        register_gateway('test_gateway', TestGateway)
        gateways = list_available_gateways()

        assert 'test_gateway' in gateways

        # Clean up
        del GATEWAY_REGISTRY['test_gateway']


class TestGatewayIntegration:
    """Integration tests for gateway factory with actual gateway instances"""

    def test_razorpay_gateway_initialization(self):
        """Test that Razorpay gateway is properly initialized"""
        gateway = get_gateway('razorpay')

        assert gateway.api_key is not None
        assert gateway.api_secret is not None
        assert hasattr(gateway, 'client')

    def test_multiple_gateway_instances_independent(self):
        """Test that multiple gateway instances are independent"""
        gateway1 = get_gateway('razorpay')
        gateway2 = get_gateway('razorpay')

        # Different instances
        assert gateway1 is not gateway2

        # But same configuration
        assert gateway1.api_key == gateway2.api_key
        assert gateway1.api_secret == gateway2.api_secret

    def test_gateway_has_all_required_methods(self):
        """Test that gateway has all required BasePaymentGateway methods"""
        gateway = get_gateway('razorpay')

        required_methods = [
            'create_customer',
            'get_customer',
            'create_subscription',
            'cancel_subscription',
            'get_subscription',
            'create_product',
            'create_price',
            'create_checkout_session',
            'get_invoice',
            'verify_webhook_signature',
            'parse_webhook_event'
        ]

        for method_name in required_methods:
            assert hasattr(gateway, method_name)
            assert callable(getattr(gateway, method_name))


class TestGatewayRegistry:
    """Tests for gateway registry behavior"""

    def test_registry_is_dict(self):
        """Test that gateway registry is a dictionary"""
        assert isinstance(GATEWAY_REGISTRY, dict)

    def test_registry_contains_razorpay(self):
        """Test that registry contains Razorpay by default"""
        assert 'razorpay' in GATEWAY_REGISTRY
        assert GATEWAY_REGISTRY['razorpay'] == RazorpayGateway

    def test_registry_keys_are_lowercase(self):
        """Test that all registry keys are lowercase"""
        for key in GATEWAY_REGISTRY.keys():
            assert key == key.lower()
