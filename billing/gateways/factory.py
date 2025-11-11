"""
Payment gateway factory.

Provides a centralized way to get payment gateway instances based on configuration.
Supports easy addition of new gateways without changing business logic.
"""

from typing import Optional
from django.conf import settings
from .base import BasePaymentGateway, GatewayException
from .razorpay_gateway import RazorpayGateway


# Gateway registry - maps gateway names to their classes
GATEWAY_REGISTRY = {
    'razorpay': RazorpayGateway,
    # Future gateways can be added here:
    # 'stripe': StripeGateway,
    # 'cashfree': CashfreeGateway,
}


def get_gateway(gateway_name: Optional[str] = None) -> BasePaymentGateway:
    """
    Get a payment gateway instance.

    Args:
        gateway_name: Name of the gateway ('razorpay', 'stripe', etc.)
                     If None, uses DEFAULT_PAYMENT_GATEWAY from settings

    Returns:
        Configured payment gateway instance

    Raises:
        GatewayException: If gateway is not supported or configuration is missing

    Example:
        >>> gateway = get_gateway('razorpay')
        >>> customer = gateway.create_customer('user@example.com', 'John Doe')
    """
    # Use default gateway if none specified
    if gateway_name is None:
        gateway_name = getattr(settings, 'DEFAULT_PAYMENT_GATEWAY', 'razorpay')

    # Normalize gateway name
    gateway_name = gateway_name.lower().strip()

    # Check if gateway is supported
    if gateway_name not in GATEWAY_REGISTRY:
        supported = ', '.join(GATEWAY_REGISTRY.keys())
        raise GatewayException(
            message=f"Unsupported payment gateway: {gateway_name}. Supported gateways: {supported}",
            error_code='unsupported_gateway'
        )

    # Get gateway class
    gateway_class = GATEWAY_REGISTRY[gateway_name]

    # Get gateway configuration from settings
    try:
        if gateway_name == 'razorpay':
            api_key = settings.RAZORPAY_KEY_ID
            api_secret = settings.RAZORPAY_KEY_SECRET
            webhook_secret = getattr(settings, 'RAZORPAY_WEBHOOK_SECRET', None)

        # Future gateways:
        # elif gateway_name == 'stripe':
        #     api_key = settings.STRIPE_PUBLIC_KEY
        #     api_secret = settings.STRIPE_SECRET_KEY
        #     webhook_secret = getattr(settings, 'STRIPE_WEBHOOK_SECRET', None)

        else:
            raise GatewayException(
                message=f"Configuration not found for gateway: {gateway_name}",
                error_code='gateway_config_missing'
            )

    except AttributeError as e:
        raise GatewayException(
            message=f"Missing configuration for {gateway_name}: {str(e)}",
            error_code='gateway_config_missing'
        )

    # Instantiate and return gateway
    return gateway_class(
        api_key=api_key,
        api_secret=api_secret,
        webhook_secret=webhook_secret
    )


def register_gateway(name: str, gateway_class: type):
    """
    Register a new payment gateway.

    Allows adding custom payment gateways at runtime.

    Args:
        name: Gateway identifier (e.g., 'custom_gateway')
        gateway_class: Gateway class that extends BasePaymentGateway

    Example:
        >>> from myapp.gateways import CustomGateway
        >>> register_gateway('custom', CustomGateway)
    """
    if not issubclass(gateway_class, BasePaymentGateway):
        raise GatewayException(
            message=f"Gateway class must extend BasePaymentGateway",
            error_code='invalid_gateway_class'
        )

    GATEWAY_REGISTRY[name.lower()] = gateway_class


def list_available_gateways():
    """
    List all registered payment gateways.

    Returns:
        List of gateway names
    """
    return list(GATEWAY_REGISTRY.keys())
