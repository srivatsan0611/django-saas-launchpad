import uuid

from django.db import models

from organizations.models import Organization


class FeatureFlag(models.Model):
    """
    Represents a feature flag that can be enabled/disabled per organization or globally.
    Global flags (organization=None) apply to all organizations.
    Organization specific flags override global defaults.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="identifier for the feature flag",
    )
    key = models.CharField(
        max_length=255,
        db_index=True,
        help_text="key identifier for the feature flag (e.g. new_dashboard)",
    )
    name = models.CharField(max_length=255, help_text="name for the feature flag")
    description = models.TextField(
        blank=True, help_text="description of what this feature flag controls"
    )
    default_enabled = models.BooleanField(
        default=False, help_text="default enabled state for this feature flag"
    )
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="feature_flags",
        help_text="Organization this flag belongs to. If null, this is a global flag.",
    )
    enabled = models.BooleanField(
        default=False, help_text="Current enabled state of the feature flag"
    )
    rules = models.JSONField(
        default=dict,
        blank=True,
        help_text="JSON object containing feature flag rules (e.g.,user targeting)",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Feature Flag"
        verbose_name_plural = "Feature Flags"
        constraints = [
            models.UniqueConstraint(
                fields=["key", "organization"], name="unique_key_per_org"
            ),
        ]
        indexes = [
            models.Index(fields=["organization", "key"]),
            models.Index(fields=["organization", "enabled"]),
        ]

    def __str__(self):
        org_name = self.organization.name if self.organization else "Global"
        return f"{org_name} - {self.name} ({self.key})"

    def is_global(self):
        """Check if this is a global feature flag (not organization-specific)"""
        return self.organization is None
