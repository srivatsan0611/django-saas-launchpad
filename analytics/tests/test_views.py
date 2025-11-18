"""
Tests for analytics views.

Tests cover:
- Event tracking 
- Event listing
- Metrics retrieval
"""

import pytest
from datetime import datetime
from django.urls import reverse
from rest_framework.test import APIClient
from django.utils.timezone import now
from analytics.models import Event, FeatureMetric, DailyMetric
from organizations.models import Organization
from accounts.models import User


@pytest.mark.django_db
class TestAnalyticsViews:

    def setup_method(self):
        self.client = APIClient()
        # Create user first
        self.user = User.objects.create_user(email="testuser@example.com", password="pass")
        # Create org with user as owner
        self.org = Organization.objects.create(name="TestOrg", owner=self.user)
        self.client.force_authenticate(user=self.user)

    def test_track_event_view(self):
        """POST /api/analytics/track/ should create an event"""
        url = reverse("track-event")
        data = {"organization": self.org.id, "name": "login", "timestamp": now()}
        response = self.client.post(url, data, format="json")
        assert response.status_code == 201 or response.status_code == 200

    def test_event_list_view(self):
        """GET /api/analytics/events/ should list org events"""
        Event.objects.create(organization=self.org, user=self.user, name="test", timestamp=now())
        url = reverse("event-list")
        response = self.client.get(url)
        assert response.status_code == 200
        assert len(response.data) >= 1

    def test_metrics_view(self):
        """GET /api/analytics/metrics/ should return key metrics"""
        FeatureMetric.objects.create(
            organization=self.org, feature_name="search", date=now().date(), usage_count=10
        )
        DailyMetric.objects.create(
            organization=self.org, date=now().date(), dau=5, new_users=2, revenue_cents=1500
        )

        url = reverse("metrics")
        params = {"org": self.org.id, "start_date": "2025-11-01", "end_date": "2025-11-12"}
        response = self.client.get(url, params)
        assert response.status_code == 200
        assert "dau" in response.data
        assert "revenue" in response.data
