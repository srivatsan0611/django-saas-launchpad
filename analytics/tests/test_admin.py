"""
Tests for analytics admin interface.

Tests cover:
- Read-only permissions for all models
- List displays and filters
- Search functionality
- Admin registration
"""
import pytest
from django.contrib.admin.sites import AdminSite
from django.utils import timezone
from django.test import RequestFactory

from accounts.models import User
from organizations.models import Organization
from analytics.models import Event, DailyMetric, MonthlyMetric, FeatureMetric
from analytics.admin import (
    EventAdmin,
    DailyMetricAdmin,
    MonthlyMetricAdmin,
    FeatureMetricAdmin
)


@pytest.mark.django_db
class TestEventAdmin:
    """Test EventAdmin interface."""

    def setup_method(self):
        """Set up test data."""
        self.site = AdminSite()
        self.admin = EventAdmin(Event, self.site)
        self.factory = RequestFactory()

        # Create users
        self.admin_user = User.objects.create_superuser(
            email='admin@example.com',
            password='adminpass123'
        )
        self.regular_user = User.objects.create_user(
            email='user@example.com',
            password='userpass123'
        )

        # Create organization
        self.org = Organization.objects.create(
            name='TestOrg',
            owner=self.admin_user
        )

        # Create event
        self.event = Event.objects.create(
            organization=self.org,
            user=self.regular_user,
            name='login',
            timestamp=timezone.now(),
            properties={'ip': '127.0.0.1'},
            ip_address='127.0.0.1',
            user_agent='TestAgent/1.0'
        )

    def test_event_admin_list_display(self):
        """Test that EventAdmin displays correct fields."""
        expected_fields = (
            'id',
            'organization',
            'user',
            'name',
            'timestamp',
            'received_at',
            'ip_address',
            'user_agent'
        )
        assert self.admin.list_display == expected_fields

    def test_event_admin_list_filter(self):
        """Test that EventAdmin has correct filters."""
        expected_filters = (
            'organization',
            'user',
            'name',
            'timestamp',
            'received_at',
            'ip_address',
            'user_agent'
        )
        assert self.admin.list_filter == expected_filters

    def test_event_admin_search_fields(self):
        """Test that EventAdmin has correct search fields."""
        expected_search = (
            'name',
            'user__username',
            'organization__name',
            'ip_address',
            'user_agent'
        )
        assert self.admin.search_fields == expected_search

    def test_event_admin_ordering(self):
        """Test that EventAdmin orders by timestamp descending."""
        assert self.admin.ordering == ('-timestamp',)

    def test_event_admin_readonly_fields(self):
        """Test that all fields are read-only."""
        expected_readonly = (
            'organization',
            'user',
            'name',
            'properties',
            'timestamp',
            'received_at',
            'ip_address',
            'user_agent'
        )
        assert self.admin.readonly_fields == expected_readonly

    def test_event_admin_has_no_add_permission(self):
        """Test that EventAdmin doesn't allow adding events."""
        request = self.factory.get('/admin/analytics/event/')
        request.user = self.admin_user
        assert not self.admin.has_add_permission(request)

    def test_event_admin_has_no_change_permission(self):
        """Test that EventAdmin doesn't allow editing events."""
        request = self.factory.get(f'/admin/analytics/event/{self.event.id}/change/')
        request.user = self.admin_user
        assert not self.admin.has_change_permission(request, self.event)

    def test_event_admin_has_no_delete_permission(self):
        """Test that EventAdmin doesn't allow deleting events."""
        request = self.factory.get(f'/admin/analytics/event/{self.event.id}/delete/')
        request.user = self.admin_user
        assert not self.admin.has_delete_permission(request, self.event)


@pytest.mark.django_db
class TestDailyMetricAdmin:
    """Test DailyMetricAdmin interface."""

    def setup_method(self):
        """Set up test data."""
        self.site = AdminSite()
        self.admin = DailyMetricAdmin(DailyMetric, self.site)
        self.factory = RequestFactory()

        # Create user and organization
        self.admin_user = User.objects.create_superuser(
            email='admin@example.com',
            password='adminpass123'
        )
        self.org = Organization.objects.create(
            name='TestOrg',
            owner=self.admin_user
        )

        # Create daily metric
        self.metric = DailyMetric.objects.create(
            organization=self.org,
            date=timezone.now().date(),
            dau=100,
            new_users=10,
            revenue_cents=5000
        )

    def test_daily_metric_admin_list_display(self):
        """Test that DailyMetricAdmin displays correct fields."""
        expected_fields = (
            'organization',
            'date',
            'dau',
            'new_users',
            'revenue_cents'
        )
        assert self.admin.list_display == expected_fields

    def test_daily_metric_admin_list_filter(self):
        """Test that DailyMetricAdmin has correct filters."""
        expected_filters = (
            'organization',
            'date',
            'dau',
            'new_users'
        )
        assert self.admin.list_filter == expected_filters

    def test_daily_metric_admin_search_fields(self):
        """Test that DailyMetricAdmin has correct search fields."""
        expected_search = ('organization__name',)
        assert self.admin.search_fields == expected_search

    def test_daily_metric_admin_ordering(self):
        """Test that DailyMetricAdmin orders by date descending."""
        assert self.admin.ordering == ('-date',)

    def test_daily_metric_admin_readonly_fields(self):
        """Test that all fields are read-only."""
        expected_readonly = (
            'organization',
            'date',
            'dau',
            'new_users',
            'revenue_cents'
        )
        assert self.admin.readonly_fields == expected_readonly

    def test_daily_metric_admin_has_no_add_permission(self):
        """Test that DailyMetricAdmin doesn't allow adding metrics."""
        request = self.factory.get('/admin/analytics/dailymetric/')
        request.user = self.admin_user
        assert not self.admin.has_add_permission(request)

    def test_daily_metric_admin_has_no_change_permission(self):
        """Test that DailyMetricAdmin doesn't allow editing metrics."""
        request = self.factory.get(f'/admin/analytics/dailymetric/{self.metric.id}/change/')
        request.user = self.admin_user
        assert not self.admin.has_change_permission(request, self.metric)

    def test_daily_metric_admin_has_no_delete_permission(self):
        """Test that DailyMetricAdmin doesn't allow deleting metrics."""
        request = self.factory.get(f'/admin/analytics/dailymetric/{self.metric.id}/delete/')
        request.user = self.admin_user
        assert not self.admin.has_delete_permission(request, self.metric)


@pytest.mark.django_db
class TestMonthlyMetricAdmin:
    """Test MonthlyMetricAdmin interface."""

    def setup_method(self):
        """Set up test data."""
        self.site = AdminSite()
        self.admin = MonthlyMetricAdmin(MonthlyMetric, self.site)
        self.factory = RequestFactory()

        # Create user and organization
        self.admin_user = User.objects.create_superuser(
            email='admin@example.com',
            password='adminpass123'
        )
        self.org = Organization.objects.create(
            name='TestOrg',
            owner=self.admin_user
        )

        # Create monthly metric
        self.metric = MonthlyMetric.objects.create(
            organization=self.org,
            year=2025,
            month=11,
            mau=500,
            mrr_cents=50000,
            churn_rate=0.05
        )

    def test_monthly_metric_admin_list_display(self):
        """Test that MonthlyMetricAdmin displays correct fields."""
        expected_fields = (
            'organization',
            'year',
            'month',
            'mau',
            'mrr_cents',
            'churn_rate'
        )
        assert self.admin.list_display == expected_fields

    def test_monthly_metric_admin_list_filter(self):
        """Test that MonthlyMetricAdmin has correct filters."""
        expected_filters = (
            'organization',
            'year',
            'month'
        )
        assert self.admin.list_filter == expected_filters

    def test_monthly_metric_admin_search_fields(self):
        """Test that MonthlyMetricAdmin has correct search fields."""
        expected_search = ('organization__name',)
        assert self.admin.search_fields == expected_search

    def test_monthly_metric_admin_ordering(self):
        """Test that MonthlyMetricAdmin orders by year and month descending."""
        assert self.admin.ordering == ('-year', '-month')

    def test_monthly_metric_admin_readonly_fields(self):
        """Test that all fields are read-only."""
        expected_readonly = (
            'organization',
            'year',
            'month',
            'mau',
            'mrr_cents',
            'churn_rate'
        )
        assert self.admin.readonly_fields == expected_readonly

    def test_monthly_metric_admin_has_no_add_permission(self):
        """Test that MonthlyMetricAdmin doesn't allow adding metrics."""
        request = self.factory.get('/admin/analytics/monthlymetric/')
        request.user = self.admin_user
        assert not self.admin.has_add_permission(request)

    def test_monthly_metric_admin_has_no_change_permission(self):
        """Test that MonthlyMetricAdmin doesn't allow editing metrics."""
        request = self.factory.get(f'/admin/analytics/monthlymetric/{self.metric.id}/change/')
        request.user = self.admin_user
        assert not self.admin.has_change_permission(request, self.metric)

    def test_monthly_metric_admin_has_no_delete_permission(self):
        """Test that MonthlyMetricAdmin doesn't allow deleting metrics."""
        request = self.factory.get(f'/admin/analytics/monthlymetric/{self.metric.id}/delete/')
        request.user = self.admin_user
        assert not self.admin.has_delete_permission(request, self.metric)


@pytest.mark.django_db
class TestFeatureMetricAdmin:
    """Test FeatureMetricAdmin interface."""

    def setup_method(self):
        """Set up test data."""
        self.site = AdminSite()
        self.admin = FeatureMetricAdmin(FeatureMetric, self.site)
        self.factory = RequestFactory()

        # Create user and organization
        self.admin_user = User.objects.create_superuser(
            email='admin@example.com',
            password='adminpass123'
        )
        self.org = Organization.objects.create(
            name='TestOrg',
            owner=self.admin_user
        )

        # Create feature metric
        self.metric = FeatureMetric.objects.create(
            organization=self.org,
            feature_name='search',
            date=timezone.now().date(),
            usage_count=150,
            unique_users=50,
            last_used_at=timezone.now()
        )

    def test_feature_metric_admin_list_display(self):
        """Test that FeatureMetricAdmin displays correct fields."""
        expected_fields = (
            'organization',
            'feature_name',
            'date',
            'usage_count',
        )
        assert self.admin.list_display == expected_fields

    def test_feature_metric_admin_list_filter(self):
        """Test that FeatureMetricAdmin has correct filters."""
        expected_filters = (
            'organization',
            'feature_name',
            'date',
        )
        assert self.admin.list_filter == expected_filters

    def test_feature_metric_admin_search_fields(self):
        """Test that FeatureMetricAdmin has correct search fields."""
        expected_search = (
            'organization__name',
            'feature_name',
            'date',
        )
        assert self.admin.search_fields == expected_search

    def test_feature_metric_admin_ordering(self):
        """Test that FeatureMetricAdmin orders by date descending."""
        assert self.admin.ordering == ('-date',)

    def test_feature_metric_admin_readonly_fields(self):
        """Test that all fields are read-only."""
        expected_readonly = (
            'organization',
            'feature_name',
            'date',
            'usage_count',
        )
        assert self.admin.readonly_fields == expected_readonly

    def test_feature_metric_admin_has_no_add_permission(self):
        """Test that FeatureMetricAdmin doesn't allow adding metrics."""
        request = self.factory.get('/admin/analytics/featuremetric/')
        request.user = self.admin_user
        assert not self.admin.has_add_permission(request)

    def test_feature_metric_admin_has_no_change_permission(self):
        """Test that FeatureMetricAdmin doesn't allow editing metrics."""
        request = self.factory.get(f'/admin/analytics/featuremetric/{self.metric.id}/change/')
        request.user = self.admin_user
        assert not self.admin.has_change_permission(request, self.metric)

    def test_feature_metric_admin_has_no_delete_permission(self):
        """Test that FeatureMetricAdmin doesn't allow deleting metrics."""
        request = self.factory.get(f'/admin/analytics/featuremetric/{self.metric.id}/delete/')
        request.user = self.admin_user
        assert not self.admin.has_delete_permission(request, self.metric)