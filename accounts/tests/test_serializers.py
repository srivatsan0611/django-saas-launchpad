"""
Tests for accounts serializers.

Tests all serializers with valid and invalid data including
RegisterSerializer, LoginSerializer, PasswordResetSerializer,
EmailVerificationSerializer, and MagicLink serializers.
"""
import pytest
import uuid
from datetime import timedelta
from django.utils import timezone
from unittest.mock import patch, Mock

from accounts.models import User, MagicLink
from accounts.serializers import (
    UserSerializer,
    RegisterSerializer,
    LoginSerializer,
    PasswordResetRequestSerializer,
    PasswordResetConfirmSerializer,
    EmailVerificationSerializer,
    RequestMagicLinkSerializer,
    VerifyMagicLinkSerializer,
)


@pytest.mark.django_db
class TestUserSerializer:
    """Test UserSerializer."""

    def test_user_serializer_fields(self):
        """Test that UserSerializer contains correct fields."""
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            first_name='John',
            last_name='Doe'
        )

        serializer = UserSerializer(user)
        data = serializer.data

        assert 'id' in data
        assert 'email' in data
        assert 'first_name' in data
        assert 'last_name' in data
        assert 'email_verified' in data
        assert 'created_at' in data
        assert 'password' not in data


@pytest.mark.django_db
class TestRegisterSerializer:
    """Test RegisterSerializer."""

    @patch('accounts.tasks.send_verification_email.delay')
    def test_register_serializer_valid_data(self, mock_email_task):
        """Test registration with valid data."""
        data = {
            'email': 'newuser@example.com',
            'password': 'ValidPass123!',
            'password_confirm': 'ValidPass123!',
            'first_name': 'John',
            'last_name': 'Doe'
        }

        serializer = RegisterSerializer(data=data)
        assert serializer.is_valid()

        user = serializer.save()

        assert user.email == 'newuser@example.com'
        assert user.first_name == 'John'
        assert user.last_name == 'Doe'
        assert user.check_password('ValidPass123!')
        assert not user.email_verified
        assert user.email_verification_token is not None
        mock_email_task.assert_called_once()

    def test_register_serializer_password_mismatch(self):
        """Test that mismatched passwords raise validation error."""
        data = {
            'email': 'test@example.com',
            'password': 'ValidPass123!',
            'password_confirm': 'DifferentPass123!',
        }

        serializer = RegisterSerializer(data=data)

        assert not serializer.is_valid()
        assert 'password_confirm' in serializer.errors

    def test_register_serializer_weak_password(self):
        """Test that weak password raises validation error."""
        data = {
            'email': 'test@example.com',
            'password': '123',
            'password_confirm': '123',
        }

        serializer = RegisterSerializer(data=data)

        assert not serializer.is_valid()
        assert 'password' in serializer.errors

    def test_register_serializer_missing_email(self):
        """Test that missing email raises validation error."""
        data = {
            'password': 'ValidPass123!',
            'password_confirm': 'ValidPass123!',
        }

        serializer = RegisterSerializer(data=data)

        assert not serializer.is_valid()
        assert 'email' in serializer.errors

    @patch('accounts.tasks.send_verification_email.delay')
    def test_register_serializer_without_optional_fields(self, mock_email_task):
        """Test registration without optional fields."""
        data = {
            'email': 'test@example.com',
            'password': 'ValidPass123!',
            'password_confirm': 'ValidPass123!',
        }

        serializer = RegisterSerializer(data=data)
        assert serializer.is_valid()

        user = serializer.save()

        assert user.email == 'test@example.com'
        assert user.first_name == ''
        assert user.last_name == ''


@pytest.mark.django_db
class TestLoginSerializer:
    """Test LoginSerializer."""

    def test_login_serializer_valid_credentials(self):
        """Test login with valid credentials."""
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )

        data = {
            'email': 'test@example.com',
            'password': 'testpass123'
        }

        serializer = LoginSerializer(data=data)

        assert serializer.is_valid()
        assert serializer.validated_data['user'] == user

    def test_login_serializer_invalid_password(self):
        """Test login with invalid password."""
        User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )

        data = {
            'email': 'test@example.com',
            'password': 'wrongpassword'
        }

        serializer = LoginSerializer(data=data)

        assert not serializer.is_valid()
        assert 'non_field_errors' in serializer.errors

    def test_login_serializer_nonexistent_user(self):
        """Test login with non-existent user."""
        data = {
            'email': 'nonexistent@example.com',
            'password': 'testpass123'
        }

        serializer = LoginSerializer(data=data)

        assert not serializer.is_valid()

    def test_login_serializer_inactive_user(self):
        """Test login with inactive user."""
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        user.is_active = False
        user.save()

        data = {
            'email': 'test@example.com',
            'password': 'testpass123'
        }

        serializer = LoginSerializer(data=data)

        assert not serializer.is_valid()

    def test_login_serializer_missing_fields(self):
        """Test login with missing fields."""
        serializer = LoginSerializer(data={})

        assert not serializer.is_valid()
        assert 'email' in serializer.errors
        assert 'password' in serializer.errors


@pytest.mark.django_db
class TestPasswordResetRequestSerializer:
    """Test PasswordResetRequestSerializer."""

    @patch('accounts.tasks.send_password_reset_email.delay')
    def test_password_reset_request_existing_user(self, mock_email_task):
        """Test password reset request for existing user."""
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )

        data = {'email': 'test@example.com'}

        serializer = PasswordResetRequestSerializer(data=data)
        assert serializer.is_valid()

        result = serializer.save()

        assert result == user
        user.refresh_from_db()
        assert user.password_reset_token is not None
        assert user.password_reset_token_expires_at is not None
        mock_email_task.assert_called_once()

    @patch('accounts.tasks.send_password_reset_email.delay')
    def test_password_reset_request_nonexistent_user(self, mock_email_task):
        """Test password reset request for non-existent user."""
        data = {'email': 'nonexistent@example.com'}

        serializer = PasswordResetRequestSerializer(data=data)
        assert serializer.is_valid()

        result = serializer.save()

        assert result is None
        mock_email_task.assert_not_called()

    def test_password_reset_request_invalid_email(self):
        """Test password reset with invalid email format."""
        data = {'email': 'invalid-email'}

        serializer = PasswordResetRequestSerializer(data=data)

        assert not serializer.is_valid()
        assert 'email' in serializer.errors


@pytest.mark.django_db
class TestPasswordResetConfirmSerializer:
    """Test PasswordResetConfirmSerializer."""

    def test_password_reset_confirm_valid(self):
        """Test password reset confirmation with valid token."""
        user = User.objects.create_user(
            email='test@example.com',
            password='oldpass123'
        )
        token = str(uuid.uuid4())
        user.password_reset_token = token
        user.password_reset_token_expires_at = timezone.now() + timedelta(hours=24)
        user.save()

        data = {
            'token': token,
            'password': 'NewValidPass123!',
            'password_confirm': 'NewValidPass123!'
        }

        serializer = PasswordResetConfirmSerializer(data=data)
        assert serializer.is_valid()

        result_user = serializer.save()

        assert result_user.check_password('NewValidPass123!')
        assert result_user.password_reset_token is None
        assert result_user.password_reset_token_expires_at is None

    def test_password_reset_confirm_expired_token(self):
        """Test password reset with expired token."""
        user = User.objects.create_user(
            email='test@example.com',
            password='oldpass123'
        )
        token = str(uuid.uuid4())
        user.password_reset_token = token
        user.password_reset_token_expires_at = timezone.now() - timedelta(hours=1)
        user.save()

        data = {
            'token': token,
            'password': 'NewValidPass123!',
            'password_confirm': 'NewValidPass123!'
        }

        serializer = PasswordResetConfirmSerializer(data=data)

        assert not serializer.is_valid()
        assert 'token' in serializer.errors

    def test_password_reset_confirm_invalid_token(self):
        """Test password reset with invalid token."""
        data = {
            'token': str(uuid.uuid4()),
            'password': 'NewValidPass123!',
            'password_confirm': 'NewValidPass123!'
        }

        serializer = PasswordResetConfirmSerializer(data=data)

        assert not serializer.is_valid()
        assert 'token' in serializer.errors

    def test_password_reset_confirm_password_mismatch(self):
        """Test password reset with mismatched passwords."""
        user = User.objects.create_user(
            email='test@example.com',
            password='oldpass123'
        )
        token = str(uuid.uuid4())
        user.password_reset_token = token
        user.password_reset_token_expires_at = timezone.now() + timedelta(hours=24)
        user.save()

        data = {
            'token': token,
            'password': 'NewValidPass123!',
            'password_confirm': 'DifferentPass123!'
        }

        serializer = PasswordResetConfirmSerializer(data=data)

        assert not serializer.is_valid()
        assert 'password_confirm' in serializer.errors


@pytest.mark.django_db
class TestEmailVerificationSerializer:
    """Test EmailVerificationSerializer."""

    def test_email_verification_valid_token(self):
        """Test email verification with valid token."""
        token = str(uuid.uuid4())
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            email_verification_token=token,
            email_verified=False
        )

        data = {'token': token}

        serializer = EmailVerificationSerializer(data=data)
        assert serializer.is_valid()

        result_user = serializer.save()

        assert result_user.email_verified
        assert result_user.email_verification_token is None

    def test_email_verification_invalid_token(self):
        """Test email verification with invalid token."""
        data = {'token': str(uuid.uuid4())}

        serializer = EmailVerificationSerializer(data=data)

        assert not serializer.is_valid()
        assert 'token' in serializer.errors

    def test_email_verification_already_verified(self):
        """Test email verification for already verified email."""
        token = str(uuid.uuid4())
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            email_verification_token=token,
            email_verified=True
        )

        data = {'token': token}

        serializer = EmailVerificationSerializer(data=data)

        assert not serializer.is_valid()
        assert 'token' in serializer.errors


@pytest.mark.django_db
class TestRequestMagicLinkSerializer:
    """Test RequestMagicLinkSerializer."""

    @patch('accounts.tasks.send_magic_link_email.delay')
    def test_request_magic_link_existing_user(self, mock_email_task):
        """Test requesting magic link for existing user."""
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )

        data = {'email': 'test@example.com'}

        serializer = RequestMagicLinkSerializer(data=data)
        assert serializer.is_valid()

        magic_link = serializer.save()

        assert magic_link is not None
        assert magic_link.user == user
        assert not magic_link.is_used
        mock_email_task.assert_called_once()

    @patch('accounts.tasks.send_magic_link_email.delay')
    def test_request_magic_link_nonexistent_user(self, mock_email_task):
        """Test requesting magic link for non-existent user."""
        data = {'email': 'nonexistent@example.com'}

        serializer = RequestMagicLinkSerializer(data=data)
        assert serializer.is_valid()

        result = serializer.save()

        assert result is None
        mock_email_task.assert_not_called()

    def test_request_magic_link_inactive_user(self):
        """Test requesting magic link for inactive user."""
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        user.is_active = False
        user.save()

        data = {'email': 'test@example.com'}

        serializer = RequestMagicLinkSerializer(data=data)

        assert not serializer.is_valid()
        assert 'email' in serializer.errors


@pytest.mark.django_db
class TestVerifyMagicLinkSerializer:
    """Test VerifyMagicLinkSerializer."""

    def test_verify_magic_link_valid(self):
        """Test verifying valid magic link."""
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        magic_link = MagicLink.objects.create(user=user)

        data = {'token': str(magic_link.token)}

        serializer = VerifyMagicLinkSerializer(data=data)
        assert serializer.is_valid()

        result_user = serializer.save()

        assert result_user == user
        magic_link.refresh_from_db()
        assert magic_link.is_used

    def test_verify_magic_link_already_used(self):
        """Test verifying already used magic link."""
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        magic_link = MagicLink.objects.create(user=user)
        magic_link.is_used = True
        magic_link.save()

        data = {'token': str(magic_link.token)}

        serializer = VerifyMagicLinkSerializer(data=data)

        assert not serializer.is_valid()
        assert 'token' in serializer.errors

    def test_verify_magic_link_expired(self):
        """Test verifying expired magic link."""
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        magic_link = MagicLink.objects.create(user=user)
        magic_link.expires_at = timezone.now() - timedelta(minutes=1)
        magic_link.save()

        data = {'token': str(magic_link.token)}

        serializer = VerifyMagicLinkSerializer(data=data)

        assert not serializer.is_valid()
        assert 'token' in serializer.errors

    def test_verify_magic_link_invalid_token(self):
        """Test verifying with invalid token."""
        data = {'token': str(uuid.uuid4())}

        serializer = VerifyMagicLinkSerializer(data=data)

        assert not serializer.is_valid()
        assert 'token' in serializer.errors

    def test_verify_magic_link_inactive_user(self):
        """Test verifying magic link for inactive user."""
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        user.is_active = False
        user.save()

        magic_link = MagicLink.objects.create(user=user)

        data = {'token': str(magic_link.token)}

        serializer = VerifyMagicLinkSerializer(data=data)

        assert not serializer.is_valid()
        assert 'token' in serializer.errors
