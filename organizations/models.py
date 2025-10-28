import uuid
from django.db import models
from django.conf import settings
from django.utils.text import slugify
from django.utils import timezone
from datetime import timedelta


class Organization(models.Model):
    """
    Represents a tenant organization (company/team) in the SaaS platform.
    Each organization can have multiple members and owns subscriptions, feature flags, etc.
    """
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for the organization"
    )
    name = models.CharField(
        max_length=255,
        help_text="Organization display name"
    )
    slug = models.SlugField(
        max_length=255,
        unique=True,
        help_text="URL-friendly identifier for the organization"
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='owned_organizations',
        help_text="User who created and owns this organization"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Organization'
        verbose_name_plural = 'Organizations'

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        """Auto-generate slug from name if not provided"""
        if not self.slug:
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 1

            # Ensure slug is unique by appending counter if needed
            while Organization.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1

            self.slug = slug

        super().save(*args, **kwargs)

    def get_member_count(self):
        """Returns the total number of members in this organization"""
        return self.memberships.count()


class Membership(models.Model):
    """
    Links users to organizations with role-based access control.
    Defines what permissions a user has within an organization.
    """
    ROLE_CHOICES = [
        ('owner', 'Owner'),
        ('admin', 'Admin'),
        ('member', 'Member'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='memberships',
        help_text="User who is a member of the organization"
    )
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='memberships',
        help_text="Organization the user belongs to"
    )
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default='member',
        help_text="User's role within the organization"
    )
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user', 'organization']
        ordering = ['-joined_at']
        verbose_name = 'Membership'
        verbose_name_plural = 'Memberships'

    def __str__(self):
        return f"{self.user.email} - {self.organization.name} ({self.role})"

    def is_owner(self):
        """Check if this membership has owner role"""
        return self.role == 'owner'

    def is_admin_or_owner(self):
        """Check if this membership has admin or owner role"""
        return self.role in ['admin', 'owner']


class Invitation(models.Model):
    """
    Represents a pending invitation to join an organization.
    Uses token-based verification with expiry for security.
    """
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('member', 'Member'),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    email = models.EmailField(
        help_text="Email address of the invited user"
    )
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='invitations',
        help_text="Organization the user is invited to"
    )
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sent_invitations',
        help_text="User who sent the invitation"
    )
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default='member',
        help_text="Role the user will have upon accepting"
    )
    token = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        help_text="Secure token for invitation verification"
    )
    expires_at = models.DateTimeField(
        help_text="When this invitation expires"
    )
    accepted_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the invitation was accepted"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['email', 'organization']
        ordering = ['-created_at']
        verbose_name = 'Invitation'
        verbose_name_plural = 'Invitations'

    def __str__(self):
        return f"Invitation for {self.email} to {self.organization.name}"

    def save(self, *args, **kwargs):
        """Set expiry date to 7 days from now if not provided"""
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(days=7)
        super().save(*args, **kwargs)

    def is_expired(self):
        """Check if the invitation has expired"""
        return timezone.now() > self.expires_at

    def is_accepted(self):
        """Check if the invitation has been accepted"""
        return self.accepted_at is not None

    def can_accept(self):
        """Check if the invitation can still be accepted"""
        return not self.is_expired() and not self.is_accepted()
