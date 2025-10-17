from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils.translation import gettext_lazy as _


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
