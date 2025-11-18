"""
Tests for accounts Celery tasks.

Tests email sending tasks with mocked email functionality.
"""
import pytest
from unittest.mock import patch, Mock
from django.core import mail

from accounts.models import User, MagicLink
from accounts.tasks import (
    send_verification_email,
    send_password_reset_email,
    send_magic_link_email
)


@pytest.mark.django_db
class TestSendVerificationEmailTask:
    """Test send_verification_email Celery task."""

    @patch('accounts.tasks.send_mail')
    def test_send_verification_email_success(self, mock_send_mail):
        """Test successful verification email sending."""
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            first_name='Test',
            last_name='User'
        )
        token = 'test-verification-token'

        result = send_verification_email(user.id, token)

        assert result['status'] == 'success'
        assert result['user_id'] == user.id
        assert result['email'] == user.email
        mock_send_mail.assert_called_once()

        # Check email arguments
        call_args = mock_send_mail.call_args
        assert 'Verify your email address' in call_args[1]['subject']
        assert user.email in call_args[1]['recipient_list']
        assert token in call_args[1]['message']

    @patch('accounts.tasks.send_mail')
    def test_send_verification_email_nonexistent_user(self, mock_send_mail):
        """Test sending verification email to non-existent user."""
        result = send_verification_email(99999, 'test-token')

        assert result['status'] == 'error'
        assert 'does not exist' in result['message']
        mock_send_mail.assert_not_called()

    @patch('accounts.tasks.send_mail')
    def test_send_verification_email_includes_verification_url(self, mock_send_mail):
        """Test that verification email includes verification URL."""
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        token = 'test-verification-token'

        send_verification_email(user.id, token)

        call_args = mock_send_mail.call_args
        email_message = call_args[1]['message']

        assert 'verify-email' in email_message
        assert token in email_message

    @patch('accounts.tasks.send_mail', side_effect=Exception('Email service error'))
    def test_send_verification_email_retry_on_failure(self, mock_send_mail):
        """Test that task retries on email sending failure."""
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )

        # Create a mock task instance
        mock_task = Mock()
        mock_task.retry.side_effect = Exception('Retry triggered')

        # Bind the task
        with patch.object(send_verification_email, 'retry') as mock_retry:
            mock_retry.side_effect = Exception('Retry triggered')

            with pytest.raises(Exception):
                send_verification_email(user.id, 'test-token')

            # Verify retry was called
            assert mock_retry.called


@pytest.mark.django_db
class TestSendPasswordResetEmailTask:
    """Test send_password_reset_email Celery task."""

    @patch('accounts.tasks.send_mail')
    def test_send_password_reset_email_success(self, mock_send_mail):
        """Test successful password reset email sending."""
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            first_name='Test',
            last_name='User'
        )
        token = 'test-reset-token'

        result = send_password_reset_email(user.id, token)

        assert result['status'] == 'success'
        assert result['user_id'] == user.id
        assert result['email'] == user.email
        mock_send_mail.assert_called_once()

        # Check email arguments
        call_args = mock_send_mail.call_args
        assert 'Reset your password' in call_args[1]['subject']
        assert user.email in call_args[1]['recipient_list']
        assert token in call_args[1]['message']

    @patch('accounts.tasks.send_mail')
    def test_send_password_reset_email_nonexistent_user(self, mock_send_mail):
        """Test sending password reset email to non-existent user."""
        result = send_password_reset_email(99999, 'test-token')

        assert result['status'] == 'error'
        assert 'does not exist' in result['message']
        mock_send_mail.assert_not_called()

    @patch('accounts.tasks.send_mail')
    def test_send_password_reset_email_includes_reset_url(self, mock_send_mail):
        """Test that password reset email includes reset URL."""
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        token = 'test-reset-token'

        send_password_reset_email(user.id, token)

        call_args = mock_send_mail.call_args
        email_message = call_args[1]['message']

        assert 'reset-password' in email_message
        assert token in email_message

    @patch('accounts.tasks.send_mail')
    def test_send_password_reset_email_includes_expiry_info(self, mock_send_mail):
        """Test that password reset email includes expiry information."""
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        token = 'test-reset-token'

        send_password_reset_email(user.id, token)

        call_args = mock_send_mail.call_args
        email_message = call_args[1]['message']

        assert '24' in email_message

    @patch('accounts.tasks.send_mail', side_effect=Exception('Email service error'))
    def test_send_password_reset_email_retry_on_failure(self, mock_send_mail):
        """Test that task retries on email sending failure."""
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )

        with patch.object(send_password_reset_email, 'retry') as mock_retry:
            mock_retry.side_effect = Exception('Retry triggered')

            with pytest.raises(Exception):
                send_password_reset_email(user.id, 'test-token')

            assert mock_retry.called


@pytest.mark.django_db
class TestSendMagicLinkEmailTask:
    """Test send_magic_link_email Celery task."""

    @patch('accounts.tasks.send_mail')
    def test_send_magic_link_email_success(self, mock_send_mail):
        """Test successful magic link email sending."""
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            first_name='Test',
            last_name='User'
        )
        magic_link = MagicLink.objects.create(user=user)

        result = send_magic_link_email(magic_link.id)

        assert result['status'] == 'success'
        assert result['magic_link_id'] == magic_link.id
        assert result['email'] == user.email
        mock_send_mail.assert_called_once()

        # Check email arguments
        call_args = mock_send_mail.call_args
        assert 'magic link' in call_args[1]['subject'].lower()
        assert user.email in call_args[1]['recipient_list']
        assert str(magic_link.token) in call_args[1]['message']

    @patch('accounts.tasks.send_mail')
    def test_send_magic_link_email_nonexistent_link(self, mock_send_mail):
        """Test sending magic link email for non-existent link."""
        result = send_magic_link_email(99999)

        assert result['status'] == 'error'
        assert 'does not exist' in result['message']
        mock_send_mail.assert_not_called()

    @patch('accounts.tasks.send_mail')
    def test_send_magic_link_email_includes_magic_url(self, mock_send_mail):
        """Test that magic link email includes magic URL."""
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        magic_link = MagicLink.objects.create(user=user)

        send_magic_link_email(magic_link.id)

        call_args = mock_send_mail.call_args
        email_message = call_args[1]['message']

        assert 'magic-link' in email_message
        assert str(magic_link.token) in email_message

    @patch('accounts.tasks.send_mail')
    def test_send_magic_link_email_includes_expiry_info(self, mock_send_mail):
        """Test that magic link email includes expiry information."""
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        magic_link = MagicLink.objects.create(user=user)

        send_magic_link_email(magic_link.id)

        call_args = mock_send_mail.call_args
        email_message = call_args[1]['message']

        assert '15' in email_message

    @patch('accounts.tasks.send_mail', side_effect=Exception('Email service error'))
    def test_send_magic_link_email_retry_on_failure(self, mock_send_mail):
        """Test that task retries on email sending failure."""
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        magic_link = MagicLink.objects.create(user=user)

        with patch.object(send_magic_link_email, 'retry') as mock_retry:
            mock_retry.side_effect = Exception('Retry triggered')

            with pytest.raises(Exception):
                send_magic_link_email(magic_link.id)

            assert mock_retry.called

    @patch('accounts.tasks.send_mail')
    def test_send_magic_link_email_uses_select_related(self, mock_send_mail):
        """Test that task efficiently fetches user with select_related."""
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        magic_link = MagicLink.objects.create(user=user)

        with patch('accounts.tasks.MagicLink.objects.select_related') as mock_select:
            mock_queryset = Mock()
            mock_queryset.get.return_value = magic_link
            mock_select.return_value = mock_queryset

            send_magic_link_email(magic_link.id)

            # Verify select_related was called with 'user'
            mock_select.assert_called_once_with('user')


@pytest.mark.django_db
class TestEmailTaskIntegration:
    """Integration tests for email tasks with Django's mail backend."""

    def test_verification_email_integration(self, settings):
        """Test verification email with Django's locmem backend."""
        # Use in-memory backend for testing
        settings.EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'

        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        token = 'test-verification-token'

        send_verification_email(user.id, token)

        # Check that email was sent
        assert len(mail.outbox) == 1
        email = mail.outbox[0]

        assert 'Verify your email address' in email.subject
        assert user.email in email.to
        assert token in email.body

    def test_password_reset_email_integration(self, settings):
        """Test password reset email with Django's locmem backend."""
        settings.EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'

        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        token = 'test-reset-token'

        send_password_reset_email(user.id, token)

        # Check that email was sent
        assert len(mail.outbox) == 1
        email = mail.outbox[0]

        assert 'Reset your password' in email.subject
        assert user.email in email.to
        assert token in email.body

    def test_magic_link_email_integration(self, settings):
        """Test magic link email with Django's locmem backend."""
        settings.EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'

        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        magic_link = MagicLink.objects.create(user=user)

        send_magic_link_email(magic_link.id)

        # Check that email was sent
        assert len(mail.outbox) == 1
        email = mail.outbox[0]

        assert 'magic link' in email.subject.lower()
        assert user.email in email.to
        assert str(magic_link.token) in email.body
