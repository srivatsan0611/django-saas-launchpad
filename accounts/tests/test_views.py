"""
Tests for accounts views.

Tests all auth endpoints including register, login, verify email,
password reset, magic links, and user profile.
"""
import pytest
import uuid
from datetime import timedelta
from django.utils import timezone
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from unittest.mock import patch

from accounts.models import User, MagicLink


@pytest.fixture
def api_client():
    """Fixture for API client."""
    return APIClient()


@pytest.fixture
def test_user(db):
    """Fixture for creating a test user."""
    return User.objects.create_user(
        email='test@example.com',
        password='testpass123',
        first_name='Test',
        last_name='User',
        email_verified=True
    )


@pytest.mark.django_db
class TestRegisterView:
    """Test user registration endpoint."""

    @patch('accounts.tasks.send_verification_email.delay')
    def test_register_success(self, mock_email_task, api_client):
        """Test successful user registration."""
        url = reverse('accounts:register')
        data = {
            'email': 'newuser@example.com',
            'password': 'ValidPass123!',
            'password_confirm': 'ValidPass123!',
            'first_name': 'New',
            'last_name': 'User'
        }

        response = api_client.post(url, data, format='json')

        assert response.status_code == status.HTTP_201_CREATED
        assert 'user' in response.data
        assert response.data['user']['email'] == 'newuser@example.com'
        assert User.objects.filter(email='newuser@example.com').exists()
        mock_email_task.assert_called_once()

    def test_register_duplicate_email(self, api_client, test_user):
        """Test registration with duplicate email."""
        url = reverse('accounts:register')
        data = {
            'email': 'test@example.com',
            'password': 'ValidPass123!',
            'password_confirm': 'ValidPass123!',
        }

        response = api_client.post(url, data, format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_register_password_mismatch(self, api_client):
        """Test registration with mismatched passwords."""
        url = reverse('accounts:register')
        data = {
            'email': 'newuser@example.com',
            'password': 'ValidPass123!',
            'password_confirm': 'DifferentPass123!',
        }

        response = api_client.post(url, data, format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_register_invalid_email(self, api_client):
        """Test registration with invalid email format."""
        url = reverse('accounts:register')
        data = {
            'email': 'invalid-email',
            'password': 'ValidPass123!',
            'password_confirm': 'ValidPass123!',
        }

        response = api_client.post(url, data, format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestLoginView:
    """Test user login endpoint."""

    def test_login_success(self, api_client, test_user):
        """Test successful login."""
        url = reverse('accounts:login')
        data = {
            'email': 'test@example.com',
            'password': 'testpass123'
        }

        response = api_client.post(url, data, format='json')

        assert response.status_code == status.HTTP_200_OK
        assert 'tokens' in response.data
        assert 'access' in response.data['tokens']
        assert 'refresh' in response.data['tokens']
        assert 'user' in response.data

    def test_login_invalid_credentials(self, api_client, test_user):
        """Test login with invalid credentials."""
        url = reverse('accounts:login')
        data = {
            'email': 'test@example.com',
            'password': 'wrongpassword'
        }

        response = api_client.post(url, data, format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_login_nonexistent_user(self, api_client):
        """Test login with non-existent user."""
        url = reverse('accounts:login')
        data = {
            'email': 'nonexistent@example.com',
            'password': 'testpass123'
        }

        response = api_client.post(url, data, format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_login_inactive_user(self, api_client, test_user):
        """Test login with inactive user."""
        test_user.is_active = False
        test_user.save()

        url = reverse('accounts:login')
        data = {
            'email': 'test@example.com',
            'password': 'testpass123'
        }

        response = api_client.post(url, data, format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestLogoutView:
    """Test user logout endpoint."""

    def test_logout_success(self, api_client, test_user):
        """Test successful logout."""
        # First login to get tokens
        api_client.force_authenticate(user=test_user)

        # Get refresh token
        from rest_framework_simplejwt.tokens import RefreshToken
        refresh = RefreshToken.for_user(test_user)

        url = reverse('accounts:logout')
        data = {'refresh_token': str(refresh)}

        response = api_client.post(url, data, format='json')

        assert response.status_code == status.HTTP_200_OK

    def test_logout_without_token(self, api_client, test_user):
        """Test logout without providing refresh token."""
        api_client.force_authenticate(user=test_user)

        url = reverse('accounts:logout')
        data = {}

        response = api_client.post(url, data, format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_logout_unauthenticated(self, api_client):
        """Test logout without authentication."""
        url = reverse('accounts:logout')
        data = {'refresh_token': 'some-token'}

        response = api_client.post(url, data, format='json')

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestVerifyEmailView:
    """Test email verification endpoint."""

    def test_verify_email_success(self, api_client):
        """Test successful email verification."""
        token = str(uuid.uuid4())
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            email_verification_token=token,
            email_verified=False
        )

        url = reverse('accounts:verify_email')
        data = {'token': token}

        response = api_client.post(url, data, format='json')

        assert response.status_code == status.HTTP_200_OK
        user.refresh_from_db()
        assert user.email_verified
        assert user.email_verification_token is None

    def test_verify_email_invalid_token(self, api_client):
        """Test email verification with invalid token."""
        url = reverse('accounts:verify_email')
        data = {'token': str(uuid.uuid4())}

        response = api_client.post(url, data, format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_verify_email_already_verified(self, api_client):
        """Test email verification for already verified email."""
        token = str(uuid.uuid4())
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            email_verification_token=token,
            email_verified=True
        )

        url = reverse('accounts:verify_email')
        data = {'token': token}

        response = api_client.post(url, data, format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestResendVerificationView:
    """Test resend verification email endpoint."""

    @patch('accounts.tasks.send_verification_email.delay')
    def test_resend_verification_success(self, mock_email_task, api_client):
        """Test successful resend of verification email."""
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            email_verified=False
        )

        url = reverse('accounts:resend_verification')
        data = {'email': 'test@example.com'}

        response = api_client.post(url, data, format='json')

        assert response.status_code == status.HTTP_200_OK
        mock_email_task.assert_called_once()

    def test_resend_verification_already_verified(self, api_client, test_user):
        """Test resend for already verified email."""
        url = reverse('accounts:resend_verification')
        data = {'email': 'test@example.com'}

        response = api_client.post(url, data, format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_resend_verification_nonexistent_user(self, api_client):
        """Test resend for non-existent user."""
        url = reverse('accounts:resend_verification')
        data = {'email': 'nonexistent@example.com'}

        response = api_client.post(url, data, format='json')

        # Should return 200 for security (don't reveal user existence)
        assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestPasswordResetRequestView:
    """Test password reset request endpoint."""

    @patch('accounts.tasks.send_password_reset_email.delay')
    def test_password_reset_request_success(self, mock_email_task, api_client, test_user):
        """Test successful password reset request."""
        url = reverse('accounts:password_reset_request')
        data = {'email': 'test@example.com'}

        response = api_client.post(url, data, format='json')

        assert response.status_code == status.HTTP_200_OK
        test_user.refresh_from_db()
        assert test_user.password_reset_token is not None
        mock_email_task.assert_called_once()

    @patch('accounts.tasks.send_password_reset_email.delay')
    def test_password_reset_request_nonexistent_user(self, mock_email_task, api_client):
        """Test password reset for non-existent user."""
        url = reverse('accounts:password_reset_request')
        data = {'email': 'nonexistent@example.com'}

        response = api_client.post(url, data, format='json')

        # Should return 200 for security (don't reveal user existence)
        assert response.status_code == status.HTTP_200_OK
        mock_email_task.assert_not_called()


@pytest.mark.django_db
class TestPasswordResetConfirmView:
    """Test password reset confirmation endpoint."""

    def test_password_reset_confirm_success(self, api_client):
        """Test successful password reset."""
        user = User.objects.create_user(
            email='test@example.com',
            password='oldpass123'
        )
        token = str(uuid.uuid4())
        user.password_reset_token = token
        user.password_reset_token_expires_at = timezone.now() + timedelta(hours=24)
        user.save()

        url = reverse('accounts:password_reset_confirm')
        data = {
            'token': token,
            'password': 'NewValidPass123!',
            'password_confirm': 'NewValidPass123!'
        }

        response = api_client.post(url, data, format='json')

        assert response.status_code == status.HTTP_200_OK
        user.refresh_from_db()
        assert user.check_password('NewValidPass123!')
        assert user.password_reset_token is None

    def test_password_reset_confirm_expired_token(self, api_client):
        """Test password reset with expired token."""
        user = User.objects.create_user(
            email='test@example.com',
            password='oldpass123'
        )
        token = str(uuid.uuid4())
        user.password_reset_token = token
        user.password_reset_token_expires_at = timezone.now() - timedelta(hours=1)
        user.save()

        url = reverse('accounts:password_reset_confirm')
        data = {
            'token': token,
            'password': 'NewValidPass123!',
            'password_confirm': 'NewValidPass123!'
        }

        response = api_client.post(url, data, format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestUserProfileView:
    """Test user profile endpoint."""

    def test_get_profile_success(self, api_client, test_user):
        """Test getting authenticated user profile."""
        api_client.force_authenticate(user=test_user)

        url = reverse('accounts:user_profile')
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['email'] == 'test@example.com'
        assert response.data['first_name'] == 'Test'

    def test_update_profile_success(self, api_client, test_user):
        """Test updating user profile."""
        api_client.force_authenticate(user=test_user)

        url = reverse('accounts:user_profile')
        data = {
            'first_name': 'Updated',
            'last_name': 'Name'
        }

        response = api_client.patch(url, data, format='json')

        assert response.status_code == status.HTTP_200_OK
        test_user.refresh_from_db()
        assert test_user.first_name == 'Updated'
        assert test_user.last_name == 'Name'

    def test_get_profile_unauthenticated(self, api_client):
        """Test getting profile without authentication."""
        url = reverse('accounts:user_profile')
        response = api_client.get(url)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestRequestMagicLinkView:
    """Test request magic link endpoint."""

    @patch('accounts.tasks.send_magic_link_email.delay')
    def test_request_magic_link_success(self, mock_email_task, api_client, test_user):
        """Test successful magic link request."""
        url = reverse('accounts:request_magic_link')
        data = {'email': 'test@example.com'}

        response = api_client.post(url, data, format='json')

        assert response.status_code == status.HTTP_200_OK
        assert MagicLink.objects.filter(user=test_user).exists()
        mock_email_task.assert_called_once()

    @patch('accounts.tasks.send_magic_link_email.delay')
    def test_request_magic_link_nonexistent_user(self, mock_email_task, api_client):
        """Test magic link request for non-existent user."""
        url = reverse('accounts:request_magic_link')
        data = {'email': 'nonexistent@example.com'}

        response = api_client.post(url, data, format='json')

        # Should return 200 for security (don't reveal user existence)
        assert response.status_code == status.HTTP_200_OK
        mock_email_task.assert_not_called()


@pytest.mark.django_db
class TestVerifyMagicLinkView:
    """Test verify magic link endpoint."""

    def test_verify_magic_link_success(self, api_client, test_user):
        """Test successful magic link verification."""
        magic_link = MagicLink.objects.create(user=test_user)

        url = reverse('accounts:verify_magic_link')
        data = {'token': str(magic_link.token)}

        response = api_client.post(url, data, format='json')

        assert response.status_code == status.HTTP_200_OK
        assert 'tokens' in response.data
        assert 'access' in response.data['tokens']
        assert 'refresh' in response.data['tokens']
        magic_link.refresh_from_db()
        assert magic_link.is_used

    def test_verify_magic_link_expired(self, api_client, test_user):
        """Test magic link verification with expired link."""
        magic_link = MagicLink.objects.create(user=test_user)
        magic_link.expires_at = timezone.now() - timedelta(minutes=1)
        magic_link.save()

        url = reverse('accounts:verify_magic_link')
        data = {'token': str(magic_link.token)}

        response = api_client.post(url, data, format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_verify_magic_link_already_used(self, api_client, test_user):
        """Test magic link verification with already used link."""
        magic_link = MagicLink.objects.create(user=test_user)
        magic_link.is_used = True
        magic_link.save()

        url = reverse('accounts:verify_magic_link')
        data = {'token': str(magic_link.token)}

        response = api_client.post(url, data, format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_verify_magic_link_invalid_token(self, api_client):
        """Test magic link verification with invalid token."""
        url = reverse('accounts:verify_magic_link')
        data = {'token': str(uuid.uuid4())}

        response = api_client.post(url, data, format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST
