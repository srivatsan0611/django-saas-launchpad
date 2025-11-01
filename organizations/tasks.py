"""
Celery tasks for the organizations app.

These tasks handle asynchronous operations like sending invitation emails.
"""
from celery import shared_task
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings

from .models import Invitation


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_invitation_email(self, invitation_id):
    """
    Send invitation email to invite a user to join an organization.

    Args:
        invitation_id (UUID): The ID of the invitation

    Returns:
        dict: Status of email sending operation
    """
    try:
        # Get the invitation with related data
        invitation = Invitation.objects.select_related(
            'organization',
            'invited_by'
        ).get(id=invitation_id)

        # Build the invitation acceptance URL
        # In production, this should use your actual domain
        accept_url = f"{settings.FRONTEND_URL if hasattr(settings, 'FRONTEND_URL') else 'http://localhost:3000'}/accept-invitation?token={invitation.token}"

        # Context for email templates
        context = {
            'invitation': invitation,
            'organization': invitation.organization,
            'invited_by': invitation.invited_by,
            'accept_url': accept_url,
            'site_name': getattr(settings, 'SITE_NAME', 'Django SaaS Launchpad'),
            'expiry_days': 7,
        }

        # Render email templates
        html_message = render_to_string('emails/invitation.html', context)
        plain_message = render_to_string('emails/invitation.txt', context)

        # Send email
        send_mail(
            subject=f'You\'re invited to join {invitation.organization.name} - {context["site_name"]}',
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[invitation.email],
            html_message=html_message,
            fail_silently=False,
        )

        return {
            'status': 'success',
            'invitation_id': str(invitation_id),
            'email': invitation.email,
            'organization': invitation.organization.name,
            'message': 'Invitation email sent successfully'
        }

    except Invitation.DoesNotExist:
        return {
            'status': 'error',
            'invitation_id': str(invitation_id),
            'message': f'Invitation with id {invitation_id} does not exist'
        }

    except Exception as exc:
        # Retry the task if it fails
        raise self.retry(exc=exc)
