"""
Celery tasks for the billing app.

These tasks handle asynchronous operations like:
- Syncing subscription status from payment gateways
- Sending billing-related email notifications
- Processing payment reminders
"""
from celery import shared_task
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
import logging

from .models import Subscription, Invoice
from .services import BillingService
from .gateways.base import GatewayException

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def sync_subscription_status(self):
    """
    Periodically sync subscription status from payment gateways.

    This task should be run periodically (e.g., every hour) to ensure
    local subscription data is in sync with the payment gateway.

    Returns:
        dict: Summary of sync operation
    """
    try:
        # Get all active and trialing subscriptions
        subscriptions = Subscription.objects.filter(
            status__in=['active', 'trialing', 'past_due', 'incomplete']
        ).select_related('plan', 'organization')

        synced_count = 0
        failed_count = 0
        failed_subscriptions = []

        for subscription in subscriptions:
            try:
                BillingService.sync_subscription_from_gateway(subscription)
                synced_count += 1
                logger.info(f"Synced subscription {subscription.id}")

            except GatewayException as e:
                failed_count += 1
                failed_subscriptions.append(str(subscription.id))
                logger.error(
                    f"Failed to sync subscription {subscription.id}: {str(e)}"
                )

            except Exception as e:
                failed_count += 1
                failed_subscriptions.append(str(subscription.id))
                logger.error(
                    f"Unexpected error syncing subscription {subscription.id}: {str(e)}",
                    exc_info=True
                )

        result = {
            'status': 'completed',
            'synced_count': synced_count,
            'failed_count': failed_count,
            'failed_subscriptions': failed_subscriptions,
            'message': f'Synced {synced_count} subscriptions, {failed_count} failed'
        }

        logger.info(f"Subscription sync task completed: {result}")
        return result

    except Exception as exc:
        logger.error(f"Critical error in sync_subscription_status task: {str(exc)}", exc_info=True)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_subscription_activated_email(self, subscription_id):
    """
    Send email notification when a subscription is activated.

    Args:
        subscription_id (UUID): The ID of the activated subscription

    Returns:
        dict: Status of email sending operation
    """
    try:
        subscription = Subscription.objects.select_related(
            'organization',
            'plan'
        ).get(id=subscription_id)

        # Build the dashboard URL
        dashboard_url = f"{getattr(settings, 'FRONTEND_URL', 'http://localhost:3000')}/dashboard"

        context = {
            'subscription': subscription,
            'organization': subscription.organization,
            'plan': subscription.plan,
            'dashboard_url': dashboard_url,
            'site_name': getattr(settings, 'SITE_NAME', 'Django SaaS Launchpad'),
        }

        # Render email templates
        html_message = render_to_string('emails/subscription_activated.html', context)
        plain_message = render_to_string('emails/subscription_activated.txt', context)

        # Send email to organization owner
        send_mail(
            subject=f'Your {subscription.plan.name} subscription is now active',
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[subscription.organization.owner.email],
            html_message=html_message,
            fail_silently=False,
        )

        logger.info(f"Subscription activated email sent for {subscription_id}")

        return {
            'status': 'success',
            'subscription_id': str(subscription_id),
            'email': subscription.organization.owner.email,
            'message': 'Subscription activated email sent successfully'
        }

    except Subscription.DoesNotExist:
        logger.error(f"Subscription {subscription_id} not found")
        return {
            'status': 'error',
            'subscription_id': str(subscription_id),
            'message': f'Subscription with id {subscription_id} does not exist'
        }

    except Exception as exc:
        logger.error(f"Error sending subscription activated email: {str(exc)}", exc_info=True)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_subscription_cancelled_email(self, subscription_id):
    """
    Send email notification when a subscription is cancelled.

    Args:
        subscription_id (UUID): The ID of the cancelled subscription

    Returns:
        dict: Status of email sending operation
    """
    try:
        subscription = Subscription.objects.select_related(
            'organization',
            'plan'
        ).get(id=subscription_id)

        context = {
            'subscription': subscription,
            'organization': subscription.organization,
            'plan': subscription.plan,
            'site_name': getattr(settings, 'SITE_NAME', 'Django SaaS Launchpad'),
            'cancel_at_period_end': subscription.cancel_at_period_end,
            'period_end_date': subscription.current_period_end,
        }

        # Render email templates
        html_message = render_to_string('emails/subscription_cancelled.html', context)
        plain_message = render_to_string('emails/subscription_cancelled.txt', context)

        # Send email to organization owner
        send_mail(
            subject=f'Your {subscription.plan.name} subscription has been cancelled',
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[subscription.organization.owner.email],
            html_message=html_message,
            fail_silently=False,
        )

        logger.info(f"Subscription cancelled email sent for {subscription_id}")

        return {
            'status': 'success',
            'subscription_id': str(subscription_id),
            'email': subscription.organization.owner.email,
            'message': 'Subscription cancelled email sent successfully'
        }

    except Subscription.DoesNotExist:
        logger.error(f"Subscription {subscription_id} not found")
        return {
            'status': 'error',
            'subscription_id': str(subscription_id),
            'message': f'Subscription with id {subscription_id} does not exist'
        }

    except Exception as exc:
        logger.error(f"Error sending subscription cancelled email: {str(exc)}", exc_info=True)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_invoice_paid_email(self, invoice_id):
    """
    Send email notification when an invoice is paid.

    Args:
        invoice_id (UUID): The ID of the paid invoice

    Returns:
        dict: Status of email sending operation
    """
    try:
        invoice = Invoice.objects.select_related(
            'organization',
            'subscription',
            'subscription__plan'
        ).get(id=invoice_id)

        context = {
            'invoice': invoice,
            'organization': invoice.organization,
            'subscription': invoice.subscription,
            'plan': invoice.subscription.plan if invoice.subscription else None,
            'site_name': getattr(settings, 'SITE_NAME', 'Django SaaS Launchpad'),
            'invoice_url': invoice.invoice_url,
        }

        # Render email templates
        html_message = render_to_string('emails/invoice_paid.html', context)
        plain_message = render_to_string('emails/invoice_paid.txt', context)

        # Send email to organization owner
        send_mail(
            subject=f'Payment receipt - {invoice.amount_display}',
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[invoice.organization.owner.email],
            html_message=html_message,
            fail_silently=False,
        )

        logger.info(f"Invoice paid email sent for {invoice_id}")

        return {
            'status': 'success',
            'invoice_id': str(invoice_id),
            'email': invoice.organization.owner.email,
            'message': 'Invoice paid email sent successfully'
        }

    except Invoice.DoesNotExist:
        logger.error(f"Invoice {invoice_id} not found")
        return {
            'status': 'error',
            'invoice_id': str(invoice_id),
            'message': f'Invoice with id {invoice_id} does not exist'
        }

    except Exception as exc:
        logger.error(f"Error sending invoice paid email: {str(exc)}", exc_info=True)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_payment_failed_email(self, invoice_id):
    """
    Send email notification when a payment fails.

    Args:
        invoice_id (UUID): The ID of the failed invoice

    Returns:
        dict: Status of email sending operation
    """
    try:
        invoice = Invoice.objects.select_related(
            'organization',
            'subscription',
            'subscription__plan'
        ).get(id=invoice_id)

        # Build the billing portal URL
        billing_url = f"{getattr(settings, 'FRONTEND_URL', 'http://localhost:3000')}/billing"

        context = {
            'invoice': invoice,
            'organization': invoice.organization,
            'subscription': invoice.subscription,
            'plan': invoice.subscription.plan if invoice.subscription else None,
            'site_name': getattr(settings, 'SITE_NAME', 'Django SaaS Launchpad'),
            'billing_url': billing_url,
            'invoice_url': invoice.invoice_url,
        }

        # Render email templates
        html_message = render_to_string('emails/payment_failed.html', context)
        plain_message = render_to_string('emails/payment_failed.txt', context)

        # Send email to organization owner
        send_mail(
            subject=f'Payment failed - Action required for {invoice.amount_display}',
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[invoice.organization.owner.email],
            html_message=html_message,
            fail_silently=False,
        )

        logger.info(f"Payment failed email sent for {invoice_id}")

        return {
            'status': 'success',
            'invoice_id': str(invoice_id),
            'email': invoice.organization.owner.email,
            'message': 'Payment failed email sent successfully'
        }

    except Invoice.DoesNotExist:
        logger.error(f"Invoice {invoice_id} not found")
        return {
            'status': 'error',
            'invoice_id': str(invoice_id),
            'message': f'Invoice with id {invoice_id} does not exist'
        }

    except Exception as exc:
        logger.error(f"Error sending payment failed email: {str(exc)}", exc_info=True)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_trial_ending_email(self):
    """
    Send email notifications for trials ending soon.

    This task should be run daily to notify organizations whose trials
    are ending within the next 3 days.

    Returns:
        dict: Summary of email sending operation
    """
    try:
        # Find subscriptions with trials ending in the next 3 days
        three_days_from_now = timezone.now() + timedelta(days=3)
        tomorrow = timezone.now() + timedelta(days=1)

        subscriptions = Subscription.objects.filter(
            status='trialing',
            trial_end__gte=tomorrow,
            trial_end__lte=three_days_from_now
        ).select_related('organization', 'plan')

        sent_count = 0
        failed_count = 0

        for subscription in subscriptions:
            try:
                days_remaining = (subscription.trial_end - timezone.now()).days

                context = {
                    'subscription': subscription,
                    'organization': subscription.organization,
                    'plan': subscription.plan,
                    'days_remaining': days_remaining,
                    'trial_end_date': subscription.trial_end,
                    'site_name': getattr(settings, 'SITE_NAME', 'Django SaaS Launchpad'),
                    'billing_url': f"{getattr(settings, 'FRONTEND_URL', 'http://localhost:3000')}/billing",
                }

                # Render email templates
                html_message = render_to_string('emails/trial_ending.html', context)
                plain_message = render_to_string('emails/trial_ending.txt', context)

                # Send email
                send_mail(
                    subject=f'Your trial ends in {days_remaining} days',
                    message=plain_message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[subscription.organization.owner.email],
                    html_message=html_message,
                    fail_silently=False,
                )

                sent_count += 1
                logger.info(f"Trial ending email sent for subscription {subscription.id}")

            except Exception as e:
                failed_count += 1
                logger.error(
                    f"Failed to send trial ending email for subscription {subscription.id}: {str(e)}",
                    exc_info=True
                )

        result = {
            'status': 'completed',
            'sent_count': sent_count,
            'failed_count': failed_count,
            'message': f'Sent {sent_count} trial ending emails, {failed_count} failed'
        }

        logger.info(f"Trial ending email task completed: {result}")
        return result

    except Exception as exc:
        logger.error(f"Critical error in send_trial_ending_email task: {str(exc)}", exc_info=True)
        raise self.retry(exc=exc)
