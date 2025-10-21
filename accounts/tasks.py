"""
Celery tasks for the accounts app.

These tasks handle asynchronous operations like sending verification emails,
password reset emails, etc.
"""
from celery import shared_task
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.utils.html import strip_tags

from .models import User


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_verification_email(self, user_id, token):
    """
    Send email verification email to user.

    Args:
        user_id (int): The ID of the user to send verification email to
        token (str): The email verification token

    Returns:
        dict: Status of email sending operation
    """
    try:
        # Get the user
        user = User.objects.get(id=user_id)

        # Build the verification URL
        # In production, this should use your actual domain
        verification_url = f"{settings.FRONTEND_URL if hasattr(settings, 'FRONTEND_URL') else 'http://localhost:3000'}/verify-email?token={token}"

        # Context for email templates
        context = {
            'user': user,
            'verification_url': verification_url,
            'site_name': getattr(settings, 'SITE_NAME', 'Django SaaS Launchpad'),
        }

        # Render email templates
        html_message = render_to_string('emails/verify_email.html', context)
        plain_message = render_to_string('emails/verify_email.txt', context)

        # Send email
        send_mail(
            subject=f'Verify your email address - {context["site_name"]}',
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )

        return {
            'status': 'success',
            'user_id': user_id,
            'email': user.email,
            'message': 'Verification email sent successfully'
        }

    except User.DoesNotExist:
        return {
            'status': 'error',
            'user_id': user_id,
            'message': f'User with id {user_id} does not exist'
        }

    except Exception as exc:
        # Retry the task if it fails
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_password_reset_email(self, user_id, token):
    """
    Send password reset email to user.

    Args:
        user_id (int): The ID of the user to send password reset email to
        token (str): The password reset token

    Returns:
        dict: Status of email sending operation
    """
    try:
        # Get the user
        user = User.objects.get(id=user_id)

        # Build the reset URL
        # In production, this should use your actual domain
        reset_url = f"{settings.FRONTEND_URL if hasattr(settings, 'FRONTEND_URL') else 'http://localhost:3000'}/reset-password?token={token}"

        # Context for email templates
        context = {
            'user': user,
            'reset_url': reset_url,
            'site_name': getattr(settings, 'SITE_NAME', 'Django SaaS Launchpad'),
            'expiry_hours': 24,
        }

        # Render email templates
        html_message = render_to_string('emails/password_reset.html', context)
        plain_message = render_to_string('emails/password_reset.txt', context)

        # Send email
        send_mail(
            subject=f'Reset your password - {context["site_name"]}',
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )

        return {
            'status': 'success',
            'user_id': user_id,
            'email': user.email,
            'message': 'Password reset email sent successfully'
        }

    except User.DoesNotExist:
        return {
            'status': 'error',
            'user_id': user_id,
            'message': f'User with id {user_id} does not exist'
        }

    except Exception as exc:
        # Retry the task if it fails
        raise self.retry(exc=exc)
