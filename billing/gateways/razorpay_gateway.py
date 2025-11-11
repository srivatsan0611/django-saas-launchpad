"""
Razorpay payment gateway implementation.

Implements the BasePaymentGateway interface for Razorpay,
handling customer management, subscriptions, and webhooks.
"""

import razorpay
import hmac
import hashlib
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from .base import BasePaymentGateway, GatewayResponse, GatewayException

logger = logging.getLogger(__name__)


class RazorpayGateway(BasePaymentGateway):
    """
    Razorpay gateway implementation.

    Provides integration with Razorpay's subscription and payment APIs.
    """

    def __init__(self, api_key: str, api_secret: str, webhook_secret: Optional[str] = None):
        """
        Initialize Razorpay client.

        Args:
            api_key: Razorpay Key ID (starts with rzp_test_ or rzp_live_)
            api_secret: Razorpay Key Secret
            webhook_secret: Webhook secret for signature verification
        """
        super().__init__(api_key, api_secret, webhook_secret)
        self.client = razorpay.Client(auth=(api_key, api_secret))

    # Customer Management

    def create_customer(self, email: str, name: Optional[str] = None, metadata: Optional[Dict] = None) -> GatewayResponse:
        """
        Create a customer in Razorpay.

        Razorpay customers are required for subscriptions.
        """
        try:
            customer_data = {
                'email': email,
                'fail_existing': '0'  # Return existing customer if email already exists
            }

            if name:
                customer_data['name'] = name

            if metadata:
                customer_data['notes'] = metadata

            customer = self.client.customer.create(data=customer_data)

            return GatewayResponse(
                success=True,
                data={
                    'customer_id': customer['id'],
                    'email': customer['email'],
                    'name': customer.get('name'),
                    'created_at': customer.get('created_at')
                },
                status_code=200,
                gateway_response=customer
            )

        except razorpay.errors.BadRequestError as e:
            logger.warning(
                "Failed to create Razorpay customer",
                extra={'email': email, 'error': str(e)}
            )
            raise GatewayException(
                message=f"Failed to create customer: {str(e)}",
                error_code='customer_creation_failed',
                gateway_response=e.args[0] if e.args else None
            )
        except Exception as e:
            logger.error(
                "Unexpected error creating Razorpay customer",
                extra={'email': email, 'error': str(e)},
                exc_info=True
            )
            raise GatewayException(
                message=f"Unexpected error creating customer: {str(e)}",
                error_code='unexpected_error'
            )

    def get_customer(self, customer_id: str) -> GatewayResponse:
        """
        Retrieve customer details from Razorpay.
        """
        try:
            customer = self.client.customer.fetch(customer_id)

            return GatewayResponse(
                success=True,
                data={
                    'customer_id': customer['id'],
                    'email': customer['email'],
                    'name': customer.get('name'),
                    'created_at': customer.get('created_at')
                },
                status_code=200,
                gateway_response=customer
            )

        except razorpay.errors.BadRequestError as e:
            logger.warning(
                "Razorpay customer not found",
                extra={'customer_id': customer_id, 'error': str(e)}
            )
            raise GatewayException(
                message=f"Customer not found: {str(e)}",
                error_code='customer_not_found',
                gateway_response=e.args[0] if e.args else None
            )

    # Subscription Management

    def create_subscription(
        self,
        customer_id: str,
        plan_id: str,
        trial_days: Optional[int] = None,
        metadata: Optional[Dict] = None
    ) -> GatewayResponse:
        """
        Create a subscription in Razorpay.

        Razorpay subscriptions are linked to plans created in the dashboard.
        """
        try:
            subscription_data = {
                'plan_id': plan_id,
                'customer_id': customer_id,
                'total_count': 12,  # Number of billing cycles (12 months for yearly)
                'quantity': 1
            }

            # Add trial period if specified
            if trial_days:
                trial_end = datetime.now() + timedelta(days=trial_days)
                subscription_data['start_at'] = int(trial_end.timestamp())

            # Add metadata as notes
            if metadata:
                subscription_data['notes'] = metadata

            subscription = self.client.subscription.create(data=subscription_data)

            return GatewayResponse(
                success=True,
                data={
                    'subscription_id': subscription['id'],
                    'status': subscription['status'],
                    'plan_id': subscription['plan_id'],
                    'customer_id': subscription['customer_id'],
                    'current_start': subscription.get('current_start'),
                    'current_end': subscription.get('current_end'),
                    'charge_at': subscription.get('charge_at'),
                    'start_at': subscription.get('start_at'),
                    'end_at': subscription.get('end_at')
                },
                status_code=201,
                gateway_response=subscription
            )

        except razorpay.errors.BadRequestError as e:
            logger.warning(
                "Failed to create Razorpay subscription",
                extra={'customer_id': customer_id, 'plan_id': plan_id, 'error': str(e)}
            )
            raise GatewayException(
                message=f"Failed to create subscription: {str(e)}",
                error_code='subscription_creation_failed',
                gateway_response=e.args[0] if e.args else None
            )

    def cancel_subscription(self, subscription_id: str, cancel_at_period_end: bool = True) -> GatewayResponse:
        """
        Cancel a subscription in Razorpay.

        Args:
            subscription_id: Razorpay subscription ID
            cancel_at_period_end: If True, cancel at end of period; if False, cancel immediately
        """
        try:
            # Razorpay requires cancel_at_cycle_end parameter
            # 1 = cancel at end of current cycle, 0 = cancel immediately
            cancel_data = {
                'cancel_at_cycle_end': 1 if cancel_at_period_end else 0
            }

            subscription = self.client.subscription.cancel(
                subscription_id=subscription_id,
                data=cancel_data
            )

            return GatewayResponse(
                success=True,
                data={
                    'subscription_id': subscription['id'],
                    'status': subscription['status'],
                    'ended_at': subscription.get('ended_at'),
                    'cancelled_at': subscription.get('cancelled_at')
                },
                status_code=200,
                gateway_response=subscription
            )

        except razorpay.errors.BadRequestError as e:
            logger.warning(
                "Failed to cancel Razorpay subscription",
                extra={'subscription_id': subscription_id, 'error': str(e)}
            )
            raise GatewayException(
                message=f"Failed to cancel subscription: {str(e)}",
                error_code='subscription_cancellation_failed',
                gateway_response=e.args[0] if e.args else None
            )

    def get_subscription(self, subscription_id: str) -> GatewayResponse:
        """
        Retrieve subscription details from Razorpay.
        """
        try:
            subscription = self.client.subscription.fetch(subscription_id)

            return GatewayResponse(
                success=True,
                data={
                    'subscription_id': subscription['id'],
                    'status': subscription['status'],
                    'plan_id': subscription['plan_id'],
                    'customer_id': subscription['customer_id'],
                    'current_start': subscription.get('current_start'),
                    'current_end': subscription.get('current_end'),
                    'ended_at': subscription.get('ended_at'),
                    'cancelled_at': subscription.get('cancelled_at')
                },
                status_code=200,
                gateway_response=subscription
            )

        except razorpay.errors.BadRequestError as e:
            raise GatewayException(
                message=f"Subscription not found: {str(e)}",
                error_code='subscription_not_found',
                gateway_response=e.args[0] if e.args else None
            )

    # Product and Pricing

    def create_product(self, name: str, description: Optional[str] = None) -> GatewayResponse:
        """
        Create a product in Razorpay.

        Note: Razorpay doesn't have a separate "product" concept.
        Plans are the primary entity. This method exists for interface compatibility.
        """
        # Razorpay doesn't have products, only plans
        # Return a mock response for consistency
        return GatewayResponse(
            success=True,
            data={
                'product_id': name.lower().replace(' ', '_'),
                'name': name,
                'description': description
            },
            status_code=200
        )

    def create_price(
        self,
        product_id: str,
        amount_cents: int,
        currency: str,
        interval: str,
        interval_count: int = 1
    ) -> GatewayResponse:
        """
        Create a plan in Razorpay.

        Razorpay plans define recurring billing.
        """
        try:
            # Map interval to Razorpay period
            period_map = {
                'month': 'monthly',
                'year': 'yearly',
                'week': 'weekly',
                'day': 'daily'
            }

            period = period_map.get(interval, 'monthly')

            plan_data = {
                'period': period,
                'interval': interval_count,
                'item': {
                    'name': product_id,
                    'amount': amount_cents,  # Amount in paise (for INR)
                    'currency': currency.upper()
                }
            }

            plan = self.client.plan.create(data=plan_data)

            return GatewayResponse(
                success=True,
                data={
                    'price_id': plan['id'],
                    'plan_id': plan['id'],
                    'period': plan['period'],
                    'interval': plan['interval'],
                    'amount': plan['item']['amount'],
                    'currency': plan['item']['currency']
                },
                status_code=201,
                gateway_response=plan
            )

        except razorpay.errors.BadRequestError as e:
            raise GatewayException(
                message=f"Failed to create plan: {str(e)}",
                error_code='plan_creation_failed',
                gateway_response=e.args[0] if e.args else None
            )

    # Checkout

    def create_checkout_session(
        self,
        customer_id: str,
        plan_id: str,
        success_url: str,
        cancel_url: str,
        metadata: Optional[Dict] = None
    ) -> GatewayResponse:
        """
        Create a payment link for subscription in Razorpay.

        Razorpay uses subscription links or hosted pages for checkout.
        """
        try:
            # Create subscription first
            subscription_response = self.create_subscription(
                customer_id=customer_id,
                plan_id=plan_id,
                metadata=metadata
            )

            subscription_id = subscription_response.data['subscription_id']

            # Get subscription details to construct checkout URL
            # In production, you'd create a payment link via Razorpay Payment Links API
            # For now, return subscription details
            checkout_url = f"https://api.razorpay.com/v1/checkout/subscription/{subscription_id}"

            return GatewayResponse(
                success=True,
                data={
                    'checkout_url': checkout_url,
                    'subscription_id': subscription_id,
                    'session_id': subscription_id  # Use subscription_id as session_id
                },
                status_code=201,
                gateway_response=subscription_response.gateway_response
            )

        except Exception as e:
            raise GatewayException(
                message=f"Failed to create checkout session: {str(e)}",
                error_code='checkout_creation_failed'
            )

    # Invoices

    def get_invoice(self, invoice_id: str) -> GatewayResponse:
        """
        Retrieve invoice details from Razorpay.
        """
        try:
            invoice = self.client.invoice.fetch(invoice_id)

            return GatewayResponse(
                success=True,
                data={
                    'invoice_id': invoice['id'],
                    'amount': invoice['amount'],
                    'currency': invoice['currency'],
                    'status': invoice['status'],
                    'customer_id': invoice.get('customer_id'),
                    'subscription_id': invoice.get('subscription_id'),
                    'created_at': invoice.get('created_at'),
                    'paid_at': invoice.get('paid_at')
                },
                status_code=200,
                gateway_response=invoice
            )

        except razorpay.errors.BadRequestError as e:
            raise GatewayException(
                message=f"Invoice not found: {str(e)}",
                error_code='invoice_not_found',
                gateway_response=e.args[0] if e.args else None
            )

    # Webhooks

    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """
        Verify Razorpay webhook signature.

        Razorpay uses HMAC SHA256 for webhook signature verification.
        """
        if not self.webhook_secret:
            raise GatewayException(
                message="Webhook secret not configured",
                error_code='webhook_secret_missing'
            )

        try:
            # Razorpay signature verification
            expected_signature = hmac.new(
                key=self.webhook_secret.encode('utf-8'),
                msg=payload,
                digestmod=hashlib.sha256
            ).hexdigest()

            return hmac.compare_digest(expected_signature, signature)

        except Exception as e:
            logger.error(
                "Failed to verify Razorpay webhook signature",
                extra={'error': str(e)},
                exc_info=True
            )
            raise GatewayException(
                message=f"Failed to verify webhook signature: {str(e)}",
                error_code='webhook_verification_failed'
            )

    def parse_webhook_event(self, payload: Dict) -> Dict[str, Any]:
        """
        Parse Razorpay webhook event into standardized format.

        Razorpay webhooks have structure:
        {
            "event": "subscription.charged",
            "payload": {...}
        }
        """
        try:
            event_type = payload.get('event')
            event_payload = payload.get('payload', {})

            # Extract subscription or payment entity
            subscription_entity = event_payload.get('subscription', {}).get('entity', {})
            payment_entity = event_payload.get('payment', {}).get('entity', {})

            return {
                'event_type': event_type,
                'event_id': subscription_entity.get('id') or payment_entity.get('id'),
                'data': {
                    'subscription': subscription_entity,
                    'payment': payment_entity,
                    'raw_payload': event_payload
                }
            }

        except Exception as e:
            raise GatewayException(
                message=f"Failed to parse webhook event: {str(e)}",
                error_code='webhook_parsing_failed'
            )
