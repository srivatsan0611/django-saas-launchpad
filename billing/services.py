from typing import Optional, Dict, Any
from django.utils import timezone
from django.db import transaction
from .models import Plan, Subscription, Invoice, PaymentMethod
from .gateways.factory import get_gateway
from .gateways.base import GatewayException
from organizations.models import Organization


class BillingService:
    """
    Service layer for billing operations.
    Handles interaction with payment gateways and local database models.
    """

    @staticmethod
    def create_subscription(
        organization: Organization,
        plan: Plan,
        trial_days: Optional[int] = None,
        metadata: Optional[Dict] = None
    ) -> Subscription:
        """
        Create a new subscription for an organization.

        Args:
            organization: Organization to subscribe
            plan: Plan to subscribe to
            trial_days: Optional trial period in days
            metadata: Additional metadata for the subscription

        Returns:
            Created Subscription instance

        Raises:
            GatewayException: If gateway operation fails
        """
        gateway = get_gateway(plan.gateway)

        # Create or get customer in payment gateway
        customer_response = gateway.create_customer(
            email=organization.owner.email,
            name=organization.name,
            metadata=metadata
        )

        if not customer_response.success:
            raise GatewayException(
                message=f"Failed to create customer: {customer_response.error_message}",
                error_code=customer_response.error_code
            )

        customer_id = customer_response.data.get('customer_id')

        # Create subscription in payment gateway
        subscription_response = gateway.create_subscription(
            customer_id=customer_id,
            plan_id=plan.gateway_price_id,
            trial_days=trial_days,
            metadata=metadata
        )

        if not subscription_response.success:
            raise GatewayException(
                message=f"Failed to create subscription: {subscription_response.error_message}",
                error_code=subscription_response.error_code
            )

        sub_data = subscription_response.data

        # Create local subscription record
        subscription = Subscription.objects.create(
            organization=organization,
            plan=plan,
            gateway=plan.gateway,
            gateway_subscription_id=sub_data.get('subscription_id'),
            gateway_customer_id=customer_id,
            status=sub_data.get('status', 'incomplete'),
            current_period_start=sub_data.get('current_period_start'),
            current_period_end=sub_data.get('current_period_end'),
            trial_end=sub_data.get('trial_end')
        )

        return subscription

    @staticmethod
    def cancel_subscription(
        subscription: Subscription,
        cancel_at_period_end: bool = True,
        reason: Optional[str] = None
    ) -> Subscription:
        """
        Cancel a subscription.

        Args:
            subscription: Subscription to cancel
            cancel_at_period_end: If True, cancel at period end; else immediately
            reason: Optional cancellation reason

        Returns:
            Updated Subscription instance

        Raises:
            GatewayException: If gateway operation fails
        """
        gateway = get_gateway(subscription.gateway)

        # Cancel in payment gateway
        cancel_response = gateway.cancel_subscription(
            subscription_id=subscription.gateway_subscription_id,
            cancel_at_period_end=cancel_at_period_end
        )

        if not cancel_response.success:
            raise GatewayException(
                message=f"Failed to cancel subscription: {cancel_response.error_message}",
                error_code=cancel_response.error_code
            )

        # Update local record
        subscription.cancel_at_period_end = cancel_at_period_end
        if not cancel_at_period_end:
            subscription.status = 'cancelled'
            subscription.cancelled_at = timezone.now()
        else:
            subscription.status = cancel_response.data.get('status', subscription.status)

        subscription.save()

        return subscription

    @staticmethod
    def sync_subscription_from_gateway(subscription: Subscription) -> Subscription:
        """
        Sync subscription data from payment gateway to local database.

        Args:
            subscription: Subscription to sync

        Returns:
            Updated Subscription instance

        Raises:
            GatewayException: If gateway operation fails
        """
        gateway = get_gateway(subscription.gateway)

        # Retrieve current subscription data from gateway
        sub_response = gateway.get_subscription(
            subscription_id=subscription.gateway_subscription_id
        )

        if not sub_response.success:
            raise GatewayException(
                message=f"Failed to retrieve subscription: {sub_response.error_message}",
                error_code=sub_response.error_code
            )

        sub_data = sub_response.data

        # Update local record
        subscription.status = sub_data.get('status', subscription.status)
        subscription.current_period_start = sub_data.get(
            'current_period_start',
            subscription.current_period_start
        )
        subscription.current_period_end = sub_data.get(
            'current_period_end',
            subscription.current_period_end
        )
        subscription.trial_end = sub_data.get('trial_end', subscription.trial_end)
        subscription.cancel_at_period_end = sub_data.get(
            'cancel_at_period_end',
            subscription.cancel_at_period_end
        )

        if sub_data.get('cancelled_at') and not subscription.cancelled_at:
            subscription.cancelled_at = sub_data['cancelled_at']

        subscription.save()

        return subscription

    @staticmethod
    @transaction.atomic
    def handle_successful_payment(invoice_data: Dict[str, Any]) -> Invoice:
        """
        Handle successful payment event from gateway webhook.
        Creates or updates invoice record and updates subscription status.

        Args:
            invoice_data: Invoice data from gateway webhook

        Returns:
            Created or updated Invoice instance

        Raises:
            KeyError: If required invoice data is missing
            Exception: If invoice or subscription update fails
        """
        try:
            gateway = invoice_data['gateway']
            gateway_invoice_id = invoice_data['gateway_invoice_id']

            # Get or create invoice
            invoice, created = Invoice.objects.get_or_create(
                gateway_invoice_id=gateway_invoice_id,
                defaults={
                    'gateway': gateway,
                    'amount_cents': invoice_data.get('amount_cents', 0),
                    'currency': invoice_data.get('currency', 'USD'),
                    'status': 'paid',
                    'issued_at': invoice_data.get('issued_at'),
                    'paid_at': timezone.now(),
                    'invoice_url': invoice_data.get('invoice_url')
                }
            )

            if not created:
                # Update existing invoice
                invoice.status = 'paid'
                invoice.paid_at = timezone.now()
                invoice.invoice_url = invoice_data.get('invoice_url', invoice.invoice_url)
                invoice.save()

            # Update subscription if linked
            gateway_subscription_id = invoice_data.get('gateway_subscription_id')
            if gateway_subscription_id:
                try:
                    subscription = Subscription.objects.get(
                        gateway_subscription_id=gateway_subscription_id
                    )
                    invoice.subscription = subscription
                    invoice.organization = subscription.organization
                    invoice.save()

                    # Update subscription status if needed
                    if subscription.status in ['past_due', 'unpaid', 'incomplete']:
                        subscription.status = 'active'
                        subscription.save()

                except Subscription.DoesNotExist:
                    logger.warning(
                        f"Subscription {gateway_subscription_id} not found for invoice {gateway_invoice_id}"
                    )
                    # Don't fail the whole transaction if subscription isn't found
                    pass
                except Exception as e:
                    logger.error(f"Failed to update subscription for invoice {gateway_invoice_id}: {e}")
                    # Re-raise to rollback transaction on subscription update failures
                    raise

            return invoice

        except KeyError as e:
            logger.error(f"Missing required invoice data: {e}")
            raise
        except Exception as e:
            logger.error(f"Payment handling failed for invoice: {e}", exc_info=True)
            raise

    @staticmethod
    @transaction.atomic
    def handle_failed_payment(invoice_data: Dict[str, Any]) -> Invoice:
        """
        Handle failed payment event from gateway webhook.
        Updates invoice status and subscription status.

        Args:
            invoice_data: Invoice data from gateway webhook

        Returns:
            Updated Invoice instance

        Raises:
            KeyError: If required invoice data is missing
            Exception: If invoice or subscription update fails
        """
        try:
            gateway = invoice_data['gateway']
            gateway_invoice_id = invoice_data['gateway_invoice_id']

            # Get or create invoice
            invoice, created = Invoice.objects.get_or_create(
                gateway_invoice_id=gateway_invoice_id,
                defaults={
                    'gateway': gateway,
                    'amount_cents': invoice_data.get('amount_cents', 0),
                    'currency': invoice_data.get('currency', 'USD'),
                    'status': 'open',
                    'issued_at': invoice_data.get('issued_at'),
                    'invoice_url': invoice_data.get('invoice_url')
                }
            )

            if not created:
                # Update existing invoice
                invoice.status = 'open'
                invoice.save()

            # Update subscription status if linked
            gateway_subscription_id = invoice_data.get('gateway_subscription_id')
            if gateway_subscription_id:
                try:
                    subscription = Subscription.objects.get(
                        gateway_subscription_id=gateway_subscription_id
                    )
                    invoice.subscription = subscription
                    invoice.organization = subscription.organization
                    invoice.save()

                    # Update subscription to past_due
                    subscription.status = 'past_due'
                    subscription.save()

                except Subscription.DoesNotExist:
                    logger.warning(
                        f"Subscription {gateway_subscription_id} not found for failed invoice {gateway_invoice_id}"
                    )
                    # Don't fail the whole transaction if subscription isn't found
                    pass
                except Exception as e:
                    logger.error(f"Failed to update subscription for failed invoice {gateway_invoice_id}: {e}")
                    # Re-raise to rollback transaction on subscription update failures
                    raise

            return invoice

        except KeyError as e:
            logger.error(f"Missing required invoice data in failed payment: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed payment handling failed for invoice: {e}", exc_info=True)
            raise

    @staticmethod
    def create_checkout_session(
        organization: Organization,
        plan: Plan,
        success_url: str,
        cancel_url: str,
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Create a checkout session for subscription signup.

        Args:
            organization: Organization to subscribe
            plan: Plan to subscribe to
            success_url: URL to redirect on success
            cancel_url: URL to redirect on cancellation
            metadata: Additional metadata for the session

        Returns:
            Dict containing checkout_url

        Raises:
            GatewayException: If gateway operation fails
        """
        gateway = get_gateway(plan.gateway)

        # First create or get customer
        customer_response = gateway.create_customer(
            email=organization.owner.email,
            name=organization.name,
            metadata=metadata
        )

        if not customer_response.success:
            raise GatewayException(
                message=f"Failed to create customer: {customer_response.error_message}",
                error_code=customer_response.error_code
            )

        customer_id = customer_response.data.get('customer_id')

        # Create checkout session
        session_response = gateway.create_checkout_session(
            customer_id=customer_id,
            plan_id=plan.gateway_price_id,
            success_url=success_url,
            cancel_url=cancel_url,
            metadata=metadata
        )

        if not session_response.success:
            raise GatewayException(
                message=f"Failed to create checkout session: {session_response.error_message}",
                error_code=session_response.error_code
            )

        return session_response.data
