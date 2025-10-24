"""
Tests for accounts models.

Tests User model creation, manager methods, email uniqueness,
and MagicLink model functionality.
"""
import pytest
from django.db import IntegrityError
from django.utils import timezone
from datetime import timedelta

from accounts.models import User, MagicLink


@pytest.mark.django_db
class TestUserManager:
    """Test custom UserManager methods."""

    def test_create_user_success(self):
        """Test creating a regular user with email and password."""
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )

        assert user.email == 'test@example.com'
        assert user.check_password('testpass123')
        assert user.is_active
        assert not user.is_staff
        assert not user.is_superuser
        assert not user.email_verified

    def test_create_user_with_extra_fields(self):
        """Test creating user with additional fields."""
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            first_name='John',
            last_name='Doe'
        )

        assert user.first_name == 'John'
        assert user.last_name == 'Doe'

    def test_create_user_without_email(self):
        """Test that creating user without email raises ValueError."""
        with pytest.raises(ValueError, match='The Email field must be set'):
            User.objects.create_user(
                email='',
                password='testpass123'
            )

    def test_create_user_normalizes_email(self):
        """Test that email is normalized (lowercase domain)."""
        user = User.objects.create_user(
            email='test@EXAMPLE.COM',
            password='testpass123'
        )

        assert user.email == 'test@example.com'

    def test_create_superuser_success(self):
        """Test creating a superuser."""
        user = User.objects.create_superuser(
            email='admin@example.com',
            password='adminpass123'
        )

        assert user.email == 'admin@example.com'
        assert user.check_password('adminpass123')
        assert user.is_active
        assert user.is_staff
        assert user.is_superuser

    def test_create_superuser_with_is_staff_false(self):
        """Test that creating superuser with is_staff=False raises ValueError."""
        with pytest.raises(ValueError, match='Superuser must have is_staff=True'):
            User.objects.create_superuser(
                email='admin@example.com',
                password='adminpass123',
                is_staff=False
            )

    def test_create_superuser_with_is_superuser_false(self):
        """Test that creating superuser with is_superuser=False raises ValueError."""
        with pytest.raises(ValueError, match='Superuser must have is_superuser=True'):
            User.objects.create_superuser(
                email='admin@example.com',
                password='adminpass123',
                is_superuser=False
            )


@pytest.mark.django_db
class TestUserModel:
    """Test User model functionality."""

    def test_user_str_representation(self):
        """Test that user __str__ returns email."""
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )

        assert str(user) == 'test@example.com'

    def test_email_uniqueness(self):
        """Test that duplicate emails are not allowed."""
        User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )

        with pytest.raises(IntegrityError):
            User.objects.create_user(
                email='test@example.com',
                password='differentpass'
            )

    def test_email_is_username_field(self):
        """Test that email is set as USERNAME_FIELD."""
        assert User.USERNAME_FIELD == 'email'

    def test_user_has_no_username_field(self):
        """Test that username field is removed."""
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )

        assert user.username is None

    def test_email_verification_defaults(self):
        """Test email verification defaults."""
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )

        assert not user.email_verified
        assert user.email_verification_token is None

    def test_password_reset_defaults(self):
        """Test password reset field defaults."""
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )

        assert user.password_reset_token is None
        assert user.password_reset_token_expires_at is None

    def test_timestamps_auto_set(self):
        """Test that created_at and updated_at are automatically set."""
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )

        assert user.created_at is not None
        assert user.updated_at is not None
        assert user.created_at <= user.updated_at

    def test_updated_at_changes_on_save(self):
        """Test that updated_at changes when model is saved."""
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )

        original_updated_at = user.updated_at

        # Make a change and save
        user.first_name = 'John'
        user.save()

        assert user.updated_at > original_updated_at


@pytest.mark.django_db
class TestMagicLinkModel:
    """Test MagicLink model functionality."""

    def test_magic_link_creation(self):
        """Test creating a magic link."""
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )

        magic_link = MagicLink.objects.create(user=user)

        assert magic_link.user == user
        assert magic_link.token is not None
        assert not magic_link.is_used
        assert magic_link.expires_at is not None

    def test_magic_link_token_is_unique(self):
        """Test that magic link tokens are unique."""
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )

        link1 = MagicLink.objects.create(user=user)
        link2 = MagicLink.objects.create(user=user)

        assert link1.token != link2.token

    def test_magic_link_auto_sets_expiry(self):
        """Test that expiry is automatically set to 15 minutes from creation."""
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )

        before_creation = timezone.now()
        magic_link = MagicLink.objects.create(user=user)
        after_creation = timezone.now()

        expected_expiry_min = before_creation + timedelta(minutes=15)
        expected_expiry_max = after_creation + timedelta(minutes=15)

        assert expected_expiry_min <= magic_link.expires_at <= expected_expiry_max

    def test_magic_link_is_expired_method(self):
        """Test is_expired method."""
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )

        # Create magic link with past expiry
        magic_link = MagicLink.objects.create(user=user)
        magic_link.expires_at = timezone.now() - timedelta(minutes=1)
        magic_link.save()

        assert magic_link.is_expired()

    def test_magic_link_is_not_expired(self):
        """Test that newly created magic link is not expired."""
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )

        magic_link = MagicLink.objects.create(user=user)

        assert not magic_link.is_expired()

    def test_magic_link_is_valid_method_unused_and_not_expired(self):
        """Test is_valid returns True for unused and not expired link."""
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )

        magic_link = MagicLink.objects.create(user=user)

        assert magic_link.is_valid()

    def test_magic_link_is_valid_method_used(self):
        """Test is_valid returns False for used link."""
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )

        magic_link = MagicLink.objects.create(user=user)
        magic_link.is_used = True
        magic_link.save()

        assert not magic_link.is_valid()

    def test_magic_link_is_valid_method_expired(self):
        """Test is_valid returns False for expired link."""
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )

        magic_link = MagicLink.objects.create(user=user)
        magic_link.expires_at = timezone.now() - timedelta(minutes=1)
        magic_link.save()

        assert not magic_link.is_valid()

    def test_magic_link_str_representation(self):
        """Test magic link __str__ method."""
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )

        magic_link = MagicLink.objects.create(user=user)

        str_repr = str(magic_link)
        assert 'test@example.com' in str_repr
        assert 'expires' in str_repr.lower()

    def test_magic_link_ordering(self):
        """Test that magic links are ordered by created_at descending."""
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )

        link1 = MagicLink.objects.create(user=user)
        link2 = MagicLink.objects.create(user=user)
        link3 = MagicLink.objects.create(user=user)

        links = MagicLink.objects.all()

        assert links[0] == link3
        assert links[1] == link2
        assert links[2] == link1

    def test_user_can_have_multiple_magic_links(self):
        """Test that a user can have multiple magic links."""
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )

        link1 = MagicLink.objects.create(user=user)
        link2 = MagicLink.objects.create(user=user)

        assert user.magic_links.count() == 2
        assert link1 in user.magic_links.all()
        assert link2 in user.magic_links.all()
