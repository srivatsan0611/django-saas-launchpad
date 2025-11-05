import uuid
from django.conf import settings
from django.db import models
from organizations.models import Organization


class Event(models.Model):
    """
    Represents a user event in the analytics system.
    """
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for the event"
    )
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='events',
        help_text="Organization this event belongs to"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='events',
        help_text="User who triggered this event (optional)"
    )
    name = models.CharField(max_length=200, db_index=True)
    properties = models.JSONField(default=dict, blank=True)   
    timestamp = models.DateTimeField(db_index=True)
    received_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["organization", "timestamp"]),
            models.Index(fields=["organization", "name", "timestamp"]),
        ]
        ordering = ["-timestamp"]

class DailyMetric(models.Model):
    """
    Tracks daily usage metrics for an organization.
    Includes DAU (Daily Active Users), new users, and revenue data.
    """
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='daily_metrics',
        help_text="Organization this metric belongs to"
    )
    date = models.DateField(db_index=True)
    dau = models.IntegerField(default=0)
    new_users = models.IntegerField(default=0)
    revenue_cents = models.BigIntegerField(default=0)

    class Meta:
        unique_together = ("organization", "date")
        indexes = [models.Index(fields=["organization", "date"])]

class MonthlyMetric(models.Model):
    """
    Tracks monthly usage metrics for an organization.
    Includes MAU (Monthly Active Users), MRR (Monthly Recurring Revenue), and churn rate.
    """
    
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='monthly_metrics',
        help_text="Organization this metric belongs to"
    )
    year = models.IntegerField()
    month = models.IntegerField()
    mau = models.IntegerField(default=0)
    mrr_cents = models.BigIntegerField(default=0)
    churn_rate = models.FloatField(null=True, blank=True)

    class Meta:
        unique_together = ("organization", "year", "month")
        indexes = [models.Index(fields=["organization", "year", "month"])]
