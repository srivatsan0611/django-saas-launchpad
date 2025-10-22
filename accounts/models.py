from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from datetime import timedelta
import uuid


class UserManager(BaseUserManager):
    """
    Custom user manager where email is the unique identifier
    instead of username for authentication.
    """

    def create_user(self, email, password=None, **extra_fields):
        """
        Create and save a regular user with the given email and password.
        """
        if not email:
            raise ValueError(_('The Email field must be set'))

        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        """
        Create and save a superuser with the given email and password.
        """
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError(_('Superuser must have is_staff=True.'))
        if extra_fields.get('is_superuser') is not True:
            raise ValueError(_('Superuser must have is_superuser=True.'))

        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    """
    Custom User model that uses email instead of username for authentication.
    Includes additional fields for email verification and password reset.
    """

    # Remove username field, we'll use email instead
    username = None

    # Make email the primary identifier
    email = models.EmailField(_('email address'), unique=True)

    # Email verification fields
    email_verified = models.BooleanField(
        _('email verified'),
        default=False,
        help_text=_('Designates whether this user has verified their email address.')
    )
    email_verification_token = models.CharField(
        _('email verification token'),
        max_length=255,
        blank=True,
        null=True
    )

    # Password reset fields
    password_reset_token = models.CharField(
        _('password reset token'),
        max_length=255,
        blank=True,
        null=True
    )
    password_reset_token_expires_at = models.DateTimeField(
        _('password reset token expires at'),
        blank=True,
        null=True
    )

    # Timestamp fields
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)

    # Set email as the username field
    USERNAME_FIELD = 'email'

    # Remove email from REQUIRED_FIELDS since it's now the USERNAME_FIELD
    REQUIRED_FIELDS = []

    # Use custom manager
    objects = UserManager()

    class Meta:
        verbose_name = _('user')
        verbose_name_plural = _('users')

    def __str__(self):
        return self.email


class MagicLink(models.Model):
    """
    Model for passwordless authentication via magic links.
    Links expire after 15 minutes and can only be used once.
    """

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='magic_links',
        verbose_name=_('user')
    )

    token = models.UUIDField(
        _('token'),
        default=uuid.uuid4,
        unique=True,
        editable=False
    )

    expires_at = models.DateTimeField(
        _('expires at'),
        help_text=_('Magic link expiration time (15 minutes from creation)')
    )

    is_used = models.BooleanField(
        _('is used'),
        default=False,
        help_text=_('Whether this magic link has been used')
    )

    created_at = models.DateTimeField(
        _('created at'),
        auto_now_add=True
    )

    class Meta:
        verbose_name = _('magic link')
        verbose_name_plural = _('magic links')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['token']),
            models.Index(fields=['user', '-created_at']),
        ]

    def __str__(self):
        return f"Magic Link for {self.user.email} (expires: {self.expires_at})"

    def save(self, *args, **kwargs):
        """
        Override save to set expiration time to 15 minutes from now if not set.
        """
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(minutes=15)
        super().save(*args, **kwargs)

    def is_expired(self):
        """
        Check if the magic link has expired.

        Returns:
            bool: True if expired, False otherwise
        """
        return timezone.now() > self.expires_at

    def is_valid(self):
        """
        Check if the magic link is valid (not expired and not used).

        Returns:
            bool: True if valid, False otherwise
        """
        return not self.is_expired() and not self.is_used
