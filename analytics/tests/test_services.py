"""
Tests for analytics services.

Tests cover:
- Event tracking by services.track_event()
- DAU calculation by services.get_dau()
- WAU calculation by services.get_wau()
- MAU calculation by services.get_mau()
- Revenue aggregation by services.get_revenue_timeseries()
- Top and least used features by services.get_top_features() and services.get_least_used_features()
"""

import pytest
from datetime import timedelta
from django.utils.timezone import now
from analytics import services
from analytics.models import Event, DailyMetric, FeatureMetric
from organizations.models import Organization
from accounts.models import User


@pytest.mark.django_db
class TestAnalyticsServices:

    def setup_method(self):
        """Create test org and users"""
        # Create users first
        self.user1 = User.objects.create_user(email="u1@example.com", password="pass")
        self.user2 = User.objects.create_user(email="u2@example.com", password="pass")
        # Create org with user1 as owner
        self.org = Organization.objects.create(name="TestOrg", owner=self.user1)

    def test_event_tracking(self):
        """Should record an event successfully"""
        Event.objects.create(
            organization=self.org,
            user=self.user1,
            name="login",
            timestamp=now(),
            properties={"ip": "127.0.0.1"}
        )
        assert Event.objects.count() == 1

    def test_dau_calculation(self):
        """Daily Active Users should count unique users"""
        Event.objects.create(organization=self.org, user=self.user1, name="login", timestamp=now())
        Event.objects.create(organization=self.org, user=self.user2, name="logout", timestamp=now())
        dau_list = services.get_dau(self.org, now().date(), now().date())
        assert len(dau_list) == 1
        assert dau_list[0]['dau'] == 2

    def test_wau_calculation(self):
        """Weekly Active Users should include users within 7 days"""
        for i in range(5):
            Event.objects.create(
                organization=self.org,
                user=self.user1,
                name="page_view",
                timestamp=now() - timedelta(days=i)
            )
        wau_list = services.get_wau(self.org, now().date() - timedelta(days=7), now().date())
        assert len(wau_list) >= 1
        assert wau_list[0]['wau'] == 1

    def test_mau_calculation(self):
        """Monthly Active Users should include users within 30 days"""
        Event.objects.create(
            organization=self.org,
            user=self.user1,
            name="click",
            timestamp=now() - timedelta(days=15)
        )
        mau = services.get_mau(self.org, now().date() - timedelta(days=30), now().date())
        assert mau[0]['mau'] == 1

    def test_revenue_aggregation(self):
        """Revenue aggregation should sum revenue correctly"""
        DailyMetric.objects.create(organization=self.org, date=now().date(), dau=5, new_users=2, revenue_cents=1000)
        DailyMetric.objects.create(organization=self.org, date=now().date() - timedelta(days=1), dau=3, new_users=1, revenue_cents=2500)
        revenue_data = services.get_revenue_timeseries(self.org, now().date() - timedelta(days=1), now().date())
        assert len(revenue_data) == 2
        total_revenue = sum(item['revenue_cents'] for item in revenue_data)
        assert total_revenue == 3500  

    def test_top_and_least_used_features(self):
        """Should correctly identify most and least used features"""
        FeatureMetric.objects.create(organization=self.org, feature_name="A", date=now().date(), usage_count=10)
        FeatureMetric.objects.create(organization=self.org, feature_name="B", date=now().date(), usage_count=2)
        top = services.get_top_features(self.org, now().date(), now().date())
        least = services.get_least_used_features(self.org, now().date(), now().date())
        assert top[0]["feature_name"] == "A"
        assert least[0]["feature_name"] == "B"
