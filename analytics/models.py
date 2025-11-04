import uuid
from django.conf import settings
from django.db import models


class Event(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey("organizations.Organization", on_delete=models.CASCADE, db_index=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
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
    organization = models.ForeignKey("organizations.Organization", on_delete=models.CASCADE)
    date = models.DateField(db_index=True)
    dau = models.IntegerField(default=0)
    new_users = models.IntegerField(default=0)
    revenue_cents = models.BigIntegerField(default=0)

    class Meta:
        unique_together = ("organization", "date")
        indexes = [models.Index(fields=["organization", "date"])]

class MonthlyMetric(models.Model):
    organization = models.ForeignKey("organizations.Organization", on_delete=models.CASCADE)
    year = models.IntegerField()
    month = models.IntegerField()
    mau = models.IntegerField(default=0)
    mrr_cents = models.BigIntegerField(default=0)
    churn_rate = models.FloatField(null=True, blank=True)

    class Meta:
        unique_together = ("organization", "year", "month")
        indexes = [models.Index(fields=["organization", "year", "month"])]
