import json
import logging
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.conf import settings
from django.utils import timezone
from django.core.mail import mail_admins
from django.db import IntegrityError

from .gateways.factory import get_gateway
from .gateways.base import GatewayException
from .models import Subscription, Invoice, WebhookEvent
from .services import BillingService

logger = logging.getLogger(__name__)


@csrf_exempt
@require_http_methods(["POST"])
def handle_razorpay_webhook(request):
    """
    Handle webhooks from Razorpay.

    Webhook events include:
    - subscription.activated
    - subscription.charged
    - subscription.cancelled
    - subscription.paused
    - subscription.resumed
    - subscription.pending
    - subscription.halted
    - payment.failed
    - invoice.paid
    """
    payload = request.body
    signature = request.headers.get('X-Razorpay-Signature', '')

    try:
        # Get Razorpay gateway for signature verification
        gateway = get_gateway('razorpay')

        # Verify webhook signature BEFORE any processing
        is_valid = gateway.verify_webhook_signature(payload, signature)
        if not is_valid:
            logger.warning("Invalid Razorpay webhook signature")
            return HttpResponse(status=400)

        # NOW parse webhook payload after signature is verified
        event_data = json.loads(payload.decode('utf-8'))
        event = gateway.parse_webhook_event(event_data)

        event_type = event.get('event_type')
        event_id = event.get('event_id')
        data = event.get('data', {})

        logger.info(f"Received Razorpay webhook: {event_type} (ID: {event_id})")

        # Check if event was already processed (idempotency)
        if WebhookEvent.objects.filter(event_id=event_id, gateway='razorpay').exists():
            logger.info(f"Event {event_id} already processed, skipping")
            return HttpResponse(status=200)

        # Route event to appropriate handler
        if event_type == 'subscription.activated':
            handle_subscription_activated(data, 'razorpay', event_id, event_data)
        elif event_type == 'subscription.charged':
            handle_subscription_charged(data, 'razorpay', event_id, event_data)
        elif event_type == 'subscription.cancelled':
            handle_subscription_cancelled(data, 'razorpay', event_id, event_data)
        elif event_type == 'subscription.paused':
            handle_subscription_paused(data, 'razorpay', event_id, event_data)
        elif event_type == 'subscription.resumed':
            handle_subscription_resumed(data, 'razorpay', event_id, event_data)
        elif event_type == 'subscription.halted':
            handle_subscription_halted(data, 'razorpay', event_id, event_data)
        elif event_type == 'payment.failed':
            handle_payment_failed(data, 'razorpay', event_id, event_data)
        elif event_type == 'invoice.paid':
            handle_invoice_paid(data, 'razorpay', event_id, event_data)
        else:
            logger.info(f"Unhandled Razorpay event type: {event_type}")

        return HttpResponse(status=200)

    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in Razorpay webhook: {str(e)}")
        return HttpResponse(status=400)
    except GatewayException as e:
        logger.error(f"Gateway exception in Razorpay webhook: {str(e)}")
        return HttpResponse(status=400)
    except Exception as e:
        logger.error(f"Error processing Razorpay webhook: {str(e)}", exc_info=True)
        return HttpResponse(status=500)


@csrf_exempt
@require_http_methods(["POST"])
def handle_generic_webhook(request, gateway_name):
    """
    Generic webhook handler for other payment gateways.
    Can be extended to support additional gateways.

    URL: /api/billing/webhooks/<gateway_name>/
    """
    payload = request.body

    # Get signature header (varies by gateway)
    signature_headers = {
        'stripe': 'Stripe-Signature',
        'paddle': 'Paddle-Signature',
    }
    signature_header = signature_headers.get(gateway_name.lower(), 'X-Signature')
    signature = request.headers.get(signature_header, '')

    try:
        # Get gateway instance
        gateway = get_gateway(gateway_name)

        # Verify webhook signature BEFORE any processing
        is_valid = gateway.verify_webhook_signature(payload, signature)
        if not is_valid:
            logger.warning(f"Invalid {gateway_name} webhook signature")
            return HttpResponse(status=400)

        # NOW parse webhook payload after signature is verified
        event_data = json.loads(payload.decode('utf-8'))
        event = gateway.parse_webhook_event(event_data)

        event_type = event.get('event_type')
        event_id = event.get('event_id')
        data = event.get('data', {})

        logger.info(f"Received {gateway_name} webhook: {event_type} (ID: {event_id})")

        # Check if event was already processed (idempotency)
        if WebhookEvent.objects.filter(event_id=event_id, gateway=gateway_name).exists():
            logger.info(f"Event {event_id} already processed, skipping")
            return HttpResponse(status=200)

        # Route to handlers (normalized event types)
        if 'subscription.activated' in event_type or 'subscription.created' in event_type:
            handle_subscription_activated(data, gateway_name, event_id, event_data)
        elif 'subscription.updated' in event_type:
            handle_subscription_updated(data, gateway_name, event_id, event_data)
        elif 'subscription.cancelled' in event_type or 'subscription.deleted' in event_type:
            handle_subscription_cancelled(data, gateway_name, event_id, event_data)
        elif 'invoice.paid' in event_type or 'payment.succeeded' in event_type:
            handle_invoice_paid(data, gateway_name, event_id, event_data)
        elif 'invoice.payment_failed' in event_type or 'payment.failed' in event_type:
            handle_payment_failed(data, gateway_name, event_id, event_data)
        else:
            logger.info(f"Unhandled {gateway_name} event type: {event_type}")

        return HttpResponse(status=200)

    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in {gateway_name} webhook: {str(e)}")
        return HttpResponse(status=400)
    except GatewayException as e:
        logger.error(f"Gateway exception in {gateway_name} webhook: {str(e)}")
        return HttpResponse(status=400)
    except Exception as e:
        logger.error(f"Error processing {gateway_name} webhook: {str(e)}", exc_info=True)
        return HttpResponse(status=500)


# Event Handlers

def handle_subscription_activated(data, gateway, event_id, event_data):
    """Handle subscription activation"""
    try:
        subscription_id = data.get('subscription_id')
        if not subscription_id:
            logger.error("No subscription_id in activation event")
            return

        subscription = Subscription.objects.get(
            gateway_subscription_id=subscription_id,
            gateway=gateway
        )

        subscription.status = 'active'
        subscription.current_period_start = data.get('current_period_start')
        subscription.current_period_end = data.get('current_period_end')
        subscription.save()

        logger.info(f"Subscription {subscription_id} activated")

        # Mark event as processed
        WebhookEvent.objects.create(
            event_id=event_id,
            event_type='subscription.activated',
            gateway=gateway,
            payload=event_data
        )

        # Trigger email notification (async)
        from .tasks import send_subscription_activated_email
        send_subscription_activated_email.delay(str(subscription.id))

    except Subscription.DoesNotExist:
        error_msg = f"Subscription {subscription_id} not found in database for gateway {gateway}"
        logger.warning(error_msg)

        # Send alert to admins for critical webhook failure
        mail_admins(
            subject="Critical: Subscription Not Found in Webhook",
            message=f"{error_msg}\n\nEvent ID: {event_id}\nEvent data: {data}",
            fail_silently=True
        )
    except Exception as e:
        logger.error(f"Error handling subscription activation: {str(e)}", exc_info=True)


def handle_subscription_updated(data, gateway, event_id, event_data):
    """Handle subscription update"""
    try:
        subscription_id = data.get('subscription_id')
        if not subscription_id:
            return

        subscription = Subscription.objects.get(
            gateway_subscription_id=subscription_id,
            gateway=gateway
        )

        # Sync from gateway to get latest data
        BillingService.sync_subscription_from_gateway(subscription)

        logger.info(f"Subscription {subscription_id} updated")

        # Mark event as processed
        WebhookEvent.objects.create(
            event_id=event_id,
            event_type='subscription.updated',
            gateway=gateway,
            payload=event_data
        )

    except Subscription.DoesNotExist:
        error_msg = f"Subscription {subscription_id} not found in database for gateway {gateway}"
        logger.warning(error_msg)

        # Send alert to admins for critical webhook failure
        mail_admins(
            subject="Critical: Subscription Not Found in Webhook",
            message=f"{error_msg}\n\nEvent ID: {event_id}\nEvent data: {data}",
            fail_silently=True
        )
    except Exception as e:
        logger.error(f"Error handling subscription update: {str(e)}", exc_info=True)


def handle_subscription_charged(data, gateway, event_id, event_data):
    """Handle subscription charge (Razorpay-specific)"""
    try:
        # This is similar to invoice.paid
        handle_invoice_paid(data, gateway, event_id, event_data)
    except Exception as e:
        logger.error(f"Error handling subscription charge: {str(e)}", exc_info=True)


def handle_subscription_cancelled(data, gateway, event_id, event_data):
    """Handle subscription cancellation"""
    try:
        subscription_id = data.get('subscription_id')
        if not subscription_id:
            return

        subscription = Subscription.objects.get(
            gateway_subscription_id=subscription_id,
            gateway=gateway
        )

        subscription.status = 'cancelled'
        subscription.cancelled_at = timezone.now()
        subscription.save()

        logger.info(f"Subscription {subscription_id} cancelled")

        # Mark event as processed
        WebhookEvent.objects.create(
            event_id=event_id,
            event_type='subscription.cancelled',
            gateway=gateway,
            payload=event_data
        )

        # Trigger email notification (async)
        from .tasks import send_subscription_cancelled_email
        send_subscription_cancelled_email.delay(str(subscription.id))

    except Subscription.DoesNotExist:
        error_msg = f"Subscription {subscription_id} not found in database for gateway {gateway}"
        logger.warning(error_msg)

        # Send alert to admins for critical webhook failure
        mail_admins(
            subject="Critical: Subscription Not Found in Webhook",
            message=f"{error_msg}\n\nEvent ID: {event_id}\nEvent data: {data}",
            fail_silently=True
        )
    except Exception as e:
        logger.error(f"Error handling subscription cancellation: {str(e)}", exc_info=True)


def handle_subscription_paused(data, gateway, event_id, event_data):
    """Handle subscription pause"""
    try:
        subscription_id = data.get('subscription_id')
        if not subscription_id:
            return

        subscription = Subscription.objects.get(
            gateway_subscription_id=subscription_id,
            gateway=gateway
        )

        subscription.status = 'paused'
        subscription.save()

        logger.info(f"Subscription {subscription_id} paused")

        # Mark event as processed
        WebhookEvent.objects.create(
            event_id=event_id,
            event_type='subscription.paused',
            gateway=gateway,
            payload=event_data
        )

    except Subscription.DoesNotExist:
        error_msg = f"Subscription {subscription_id} not found in database for gateway {gateway}"
        logger.warning(error_msg)

        # Send alert to admins for critical webhook failure
        mail_admins(
            subject="Critical: Subscription Not Found in Webhook",
            message=f"{error_msg}\n\nEvent ID: {event_id}\nEvent data: {data}",
            fail_silently=True
        )
    except Exception as e:
        logger.error(f"Error handling subscription pause: {str(e)}", exc_info=True)


def handle_subscription_resumed(data, gateway, event_id, event_data):
    """Handle subscription resumption"""
    try:
        subscription_id = data.get('subscription_id')
        if not subscription_id:
            return

        subscription = Subscription.objects.get(
            gateway_subscription_id=subscription_id,
            gateway=gateway
        )

        subscription.status = 'active'
        subscription.save()

        logger.info(f"Subscription {subscription_id} resumed")

        # Mark event as processed
        WebhookEvent.objects.create(
            event_id=event_id,
            event_type='subscription.resumed',
            gateway=gateway,
            payload=event_data
        )

    except Subscription.DoesNotExist:
        error_msg = f"Subscription {subscription_id} not found in database for gateway {gateway}"
        logger.warning(error_msg)

        # Send alert to admins for critical webhook failure
        mail_admins(
            subject="Critical: Subscription Not Found in Webhook",
            message=f"{error_msg}\n\nEvent ID: {event_id}\nEvent data: {data}",
            fail_silently=True
        )
    except Exception as e:
        logger.error(f"Error handling subscription resume: {str(e)}", exc_info=True)


def handle_subscription_halted(data, gateway, event_id, event_data):
    """Handle subscription halt (Razorpay-specific)"""
    try:
        subscription_id = data.get('subscription_id')
        if not subscription_id:
            return

        subscription = Subscription.objects.get(
            gateway_subscription_id=subscription_id,
            gateway=gateway
        )

        subscription.status = 'unpaid'
        subscription.save()

        logger.info(f"Subscription {subscription_id} halted")

        # Mark event as processed
        WebhookEvent.objects.create(
            event_id=event_id,
            event_type='subscription.halted',
            gateway=gateway,
            payload=event_data
        )

    except Subscription.DoesNotExist:
        error_msg = f"Subscription {subscription_id} not found in database for gateway {gateway}"
        logger.warning(error_msg)

        # Send alert to admins for critical webhook failure
        mail_admins(
            subject="Critical: Subscription Not Found in Webhook",
            message=f"{error_msg}\n\nEvent ID: {event_id}\nEvent data: {data}",
            fail_silently=True
        )
    except Exception as e:
        logger.error(f"Error handling subscription halt: {str(e)}", exc_info=True)


def handle_invoice_paid(data, gateway, event_id, event_data):
    """Handle successful invoice payment"""
    try:
        invoice_data = {
            'gateway': gateway,
            'gateway_invoice_id': data.get('invoice_id'),
            'gateway_subscription_id': data.get('subscription_id'),
            'amount_cents': data.get('amount_cents'),
            'currency': data.get('currency', 'USD'),
            'issued_at': data.get('issued_at'),
            'invoice_url': data.get('invoice_url')
        }

        invoice = BillingService.handle_successful_payment(invoice_data)

        logger.info(f"Invoice {invoice.gateway_invoice_id} paid successfully")

        # Mark event as processed
        WebhookEvent.objects.create(
            event_id=event_id,
            event_type='invoice.paid',
            gateway=gateway,
            payload=event_data
        )

        # Trigger email notification (async)
        from .tasks import send_invoice_paid_email
        send_invoice_paid_email.delay(str(invoice.id))

    except Exception as e:
        logger.error(f"Error handling invoice payment: {str(e)}", exc_info=True)

        # Send alert to admins for critical webhook failure
        mail_admins(
            subject="Critical: Invoice Payment Processing Failed",
            message=f"Failed to process invoice payment\n\nEvent ID: {event_id}\nError: {str(e)}\nEvent data: {data}",
            fail_silently=True
        )


def handle_payment_failed(data, gateway, event_id, event_data):
    """Handle failed payment"""
    try:
        invoice_data = {
            'gateway': gateway,
            'gateway_invoice_id': data.get('invoice_id'),
            'gateway_subscription_id': data.get('subscription_id'),
            'amount_cents': data.get('amount_cents'),
            'currency': data.get('currency', 'USD'),
            'issued_at': data.get('issued_at'),
            'invoice_url': data.get('invoice_url')
        }

        invoice = BillingService.handle_failed_payment(invoice_data)

        logger.info(f"Payment failed for invoice {invoice.gateway_invoice_id}")

        # Mark event as processed
        WebhookEvent.objects.create(
            event_id=event_id,
            event_type='payment.failed',
            gateway=gateway,
            payload=event_data
        )

        # Trigger email notification (async)
        from .tasks import send_payment_failed_email
        send_payment_failed_email.delay(str(invoice.id))

    except Exception as e:
        logger.error(f"Error handling payment failure: {str(e)}", exc_info=True)

        # Send alert to admins for critical webhook failure
        mail_admins(
            subject="Critical: Payment Failure Processing Failed",
            message=f"Failed to process payment failure event\n\nEvent ID: {event_id}\nError: {str(e)}\nEvent data: {data}",
            fail_silently=True
        )
