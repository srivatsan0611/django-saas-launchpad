"""
Base classes for payment gateway abstraction.

This module defines the interface that all payment gateways must implement,
enabling easy switching between different payment providers (Razorpay, Stripe, etc.)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Dict, Any
from datetime import datetime


@dataclass
class GatewayResponse:
    """
    Standardized response from payment gateway operations.

    All gateway methods return this response format to ensure consistency
    across different payment providers.

    Attributes:
        success: Whether the operation succeeded
        data: Response data from the gateway
        status_code: HTTP status code or custom status (200=success, 400=bad request, etc.)
        error_message: Human-readable error message if operation failed
        error_code: Machine-readable error code for programmatic handling
        gateway_response: Raw gateway response for debugging and logging
    """
    success: bool
    data: Dict[str, Any]
    status_code: Optional[int] = None
    error_message: Optional[str] = None
    error_code: Optional[str] = None
    gateway_response: Optional[Dict[str, Any]] = None  # Raw gateway response for debugging


class GatewayException(Exception):
    """
    Custom exception for payment gateway errors.

    Raised when gateway operations fail, containing details about the failure.
    """
    def __init__(self, message: str, error_code: Optional[str] = None, gateway_response: Optional[Dict] = None):
        self.message = message
        self.error_code = error_code
        self.gateway_response = gateway_response
        super().__init__(self.message)


class BasePaymentGateway(ABC):
    """
    Abstract base class for payment gateway implementations.

    All payment gateways must implement these methods to ensure consistent
    behavior across different providers. This enables the application to
    switch between gateways without changing business logic.

    Methods:
        - Customer management (create, retrieve, update)
        - Subscription management (create, cancel, retrieve)
        - Product and pricing (create products and price plans)
        - Checkout (create payment sessions)
        - Invoices (retrieve invoice details)
        - Webhooks (verify signatures)
    """

    def __init__(self, api_key: str, api_secret: str, webhook_secret: Optional[str] = None):
        """
        Initialize the payment gateway.

        Args:
            api_key: Public/publishable API key
            api_secret: Secret API key
            webhook_secret: Secret for verifying webhook signatures
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.webhook_secret = webhook_secret

    # Customer Management

    @abstractmethod
    def create_customer(self, email: str, name: Optional[str] = None, metadata: Optional[Dict] = None) -> GatewayResponse:
        """
        Create a customer in the payment gateway.

        Args:
            email: Customer email address
            name: Customer name
            metadata: Additional metadata to attach to customer

        Returns:
            GatewayResponse with customer_id in data
        """
        pass

    @abstractmethod
    def get_customer(self, customer_id: str) -> GatewayResponse:
        """
        Retrieve customer details from the payment gateway.

        Args:
            customer_id: Gateway customer ID

        Returns:
            GatewayResponse with customer details in data
        """
        pass

    # Subscription Management

    @abstractmethod
    def create_subscription(
        self,
        customer_id: str,
        plan_id: str,
        trial_days: Optional[int] = None,
        metadata: Optional[Dict] = None
    ) -> GatewayResponse:
        """
        Create a subscription for a customer.

        Args:
            customer_id: Gateway customer ID
            plan_id: Gateway plan/price ID
            trial_days: Number of trial days (if applicable)
            metadata: Additional metadata

        Returns:
            GatewayResponse with subscription_id, status, current_period_end in data
        """
        pass

    @abstractmethod
    def cancel_subscription(self, subscription_id: str, cancel_at_period_end: bool = True) -> GatewayResponse:
        """
        Cancel a subscription.

        Args:
            subscription_id: Gateway subscription ID
            cancel_at_period_end: If True, cancel at end of billing period; if False, cancel immediately

        Returns:
            GatewayResponse with updated subscription status
        """
        pass

    @abstractmethod
    def get_subscription(self, subscription_id: str) -> GatewayResponse:
        """
        Retrieve subscription details.

        Args:
            subscription_id: Gateway subscription ID

        Returns:
            GatewayResponse with subscription details in data
        """
        pass

    # Product and Pricing

    @abstractmethod
    def create_product(self, name: str, description: Optional[str] = None) -> GatewayResponse:
        """
        Create a product in the payment gateway.

        Args:
            name: Product name
            description: Product description

        Returns:
            GatewayResponse with product_id in data
        """
        pass

    @abstractmethod
    def create_price(
        self,
        product_id: str,
        amount_cents: int,
        currency: str,
        interval: str,
        interval_count: int = 1
    ) -> GatewayResponse:
        """
        Create a price/plan for a product.

        Args:
            product_id: Gateway product ID
            amount_cents: Price in smallest currency unit (e.g., cents, paise)
            currency: Currency code (e.g., 'usd', 'inr')
            interval: Billing interval ('month', 'year')
            interval_count: Number of intervals between billings

        Returns:
            GatewayResponse with price_id/plan_id in data
        """
        pass

    # Checkout

    @abstractmethod
    def create_checkout_session(
        self,
        customer_id: str,
        plan_id: str,
        success_url: str,
        cancel_url: str,
        metadata: Optional[Dict] = None
    ) -> GatewayResponse:
        """
        Create a checkout session for payment.

        Args:
            customer_id: Gateway customer ID
            plan_id: Gateway plan/price ID
            success_url: URL to redirect after successful payment
            cancel_url: URL to redirect after cancelled payment
            metadata: Additional metadata

        Returns:
            GatewayResponse with checkout_url in data
        """
        pass

    # Invoices

    @abstractmethod
    def get_invoice(self, invoice_id: str) -> GatewayResponse:
        """
        Retrieve invoice details.

        Args:
            invoice_id: Gateway invoice ID

        Returns:
            GatewayResponse with invoice details in data
        """
        pass

    # Webhooks

    @abstractmethod
    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """
        Verify webhook signature to ensure request is from the gateway.

        Args:
            payload: Raw webhook payload
            signature: Signature from webhook headers

        Returns:
            True if signature is valid, False otherwise
        """
        pass

    @abstractmethod
    def parse_webhook_event(self, payload: Dict) -> Dict[str, Any]:
        """
        Parse webhook event payload into standardized format.

        Args:
            payload: Webhook payload dictionary

        Returns:
            Standardized event dictionary with keys:
                - event_type: str (e.g., 'subscription.created', 'payment.failed')
                - event_id: str
                - data: Dict containing event data
        """
        pass
