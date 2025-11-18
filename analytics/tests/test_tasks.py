"""
Tests for analytics Celery tasks.

Tests cover:
- Daily metrics aggregation task
- Monthly metrics aggregation task
- Feature metrics aggregation task
- Task retry behavior on failures
- Edge cases (no data, multiple organizations)
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, Mock
from django.utils import timezone

from accounts.models import User
from organizations.models import Organization
from analytics.models import Event, DailyMetric, MonthlyMetric, FeatureMetric
from analytics.tasks import (
    aggregate_daily_metrics,
    aggregate_monthly_metrics,
    aggregate_feature_metrics
)


@pytest.mark.django_db
class TestAggregateDailyMetricsTask:
    """Test aggregate_daily_metrics Celery task."""

    def setup_method(self):
        """Set up test data."""
        # Create users
        self.user1 = User.objects.create_user(
            email='user1@example.com',
            password='pass123'
        )
        self.user2 = User.objects.create_user(
            email='user2@example.com',
            password='pass123'
        )

        # Create organizations
        self.org1 = Organization.objects.create(
            name='Org1',
            owner=self.user1
        )
        self.org2 = Organization.objects.create(
            name='Org2',
            owner=self.user2
        )

    def test_aggregate_daily_metrics_success(self):
        """Test successful daily metrics aggregation."""
        yesterday = timezone.now().date() - timedelta(days=1)

        # Create events for yesterday
        Event.objects.create(
            organization=self.org1,
            user=self.user1,
            name='login',
            timestamp=timezone.make_aware(
                datetime.combine(yesterday, datetime.min.time())
            )
        )
        Event.objects.create(
            organization=self.org1,
            user=self.user2,
            name='page_view',
            timestamp=timezone.make_aware(
                datetime.combine(yesterday, datetime.min.time())
            )
        )

        # Run task
        result = aggregate_daily_metrics()

        # Check result
        assert result['status'] == 'success'
        assert str(yesterday) in result['message']

        # Check that metrics were created
        metric = DailyMetric.objects.get(organization=self.org1, date=yesterday)
        assert metric.dau == 2  # Two distinct users
        assert metric.new_users >= 0

    def test_aggregate_daily_metrics_multiple_orgs(self):
        """Test that metrics are calculated separately for each organization."""
        yesterday = timezone.now().date() - timedelta(days=1)

        # Create events for org1
        Event.objects.create(
            organization=self.org1,
            user=self.user1,
            name='login',
            timestamp=timezone.make_aware(
                datetime.combine(yesterday, datetime.min.time())
            )
        )

        # Create events for org2
        Event.objects.create(
            organization=self.org2,
            user=self.user2,
            name='login',
            timestamp=timezone.make_aware(
                datetime.combine(yesterday, datetime.min.time())
            )
        )

        # Run task
        aggregate_daily_metrics()

        # Check that metrics were created for both orgs
        metric1 = DailyMetric.objects.get(organization=self.org1, date=yesterday)
        metric2 = DailyMetric.objects.get(organization=self.org2, date=yesterday)

        assert metric1.dau == 1
        assert metric2.dau == 1

    def test_aggregate_daily_metrics_no_events(self):
        """Test that task handles organizations with no events."""
        yesterday = timezone.now().date() - timedelta(days=1)

        # Run task without creating any events
        result = aggregate_daily_metrics()

        # Task should still succeed
        assert result['status'] == 'success'

        # Check that metrics were created with zero values
        metric = DailyMetric.objects.get(organization=self.org1, date=yesterday)
        assert metric.dau == 0
        assert metric.new_users == 0

    def test_aggregate_daily_metrics_updates_existing(self):
        """Test that task updates existing metrics instead of duplicating."""
        yesterday = timezone.now().date() - timedelta(days=1)

        # Create initial metric
        DailyMetric.objects.create(
            organization=self.org1,
            date=yesterday,
            dau=5,
            new_users=2,
            revenue_cents=1000
        )

        # Create event
        Event.objects.create(
            organization=self.org1,
            user=self.user1,
            name='login',
            timestamp=timezone.make_aware(
                datetime.combine(yesterday, datetime.min.time())
            )
        )

        # Run task
        aggregate_daily_metrics()

        # Check that only one metric exists and it was updated
        metrics = DailyMetric.objects.filter(organization=self.org1, date=yesterday)
        assert metrics.count() == 1
        assert metrics.first().dau == 1  # Updated value

    def test_aggregate_daily_metrics_counts_distinct_users(self):
        """Test that DAU counts distinct users, not total events."""
        yesterday = timezone.now().date() - timedelta(days=1)

        # Create multiple events from same user
        for i in range(5):
            Event.objects.create(
                organization=self.org1,
                user=self.user1,
                name=f'event_{i}',
                timestamp=timezone.make_aware(
                    datetime.combine(yesterday, datetime.min.time()) + timedelta(hours=i)
                )
            )

        # Run task
        aggregate_daily_metrics()

        # Check that DAU is 1, not 5
        metric = DailyMetric.objects.get(organization=self.org1, date=yesterday)
        assert metric.dau == 1

    @patch('analytics.tasks.aggregate_daily_metrics.retry')
    def test_aggregate_daily_metrics_retry_on_error(self, mock_retry):
        """Test that task retries on exception."""
        mock_retry.side_effect = Exception('Retry triggered')

        # Patch Organization.objects.all() to raise an exception
        with patch('analytics.tasks.Organization.objects.all', side_effect=Exception('Database error')):
            with pytest.raises(Exception):
                aggregate_daily_metrics()

            # Verify retry was called
            assert mock_retry.called


@pytest.mark.django_db
class TestAggregateMonthlyMetricsTask:
    """Test aggregate_monthly_metrics Celery task."""

    def setup_method(self):
        """Set up test data."""
        # Create users
        self.user1 = User.objects.create_user(
            email='user1@example.com',
            password='pass123'
        )
        self.user2 = User.objects.create_user(
            email='user2@example.com',
            password='pass123'
        )

        # Create organization
        self.org = Organization.objects.create(
            name='TestOrg',
            owner=self.user1
        )

    def test_aggregate_monthly_metrics_success(self):
        """Test successful monthly metrics aggregation."""
        # Get last month's date
        today = timezone.now().date()
        first_day = today.replace(day=1)
        last_month_end = first_day - timedelta(days=1)

        # Create events for last month
        Event.objects.create(
            organization=self.org,
            user=self.user1,
            name='login',
            timestamp=timezone.make_aware(
                datetime.combine(last_month_end, datetime.min.time())
            )
        )
        Event.objects.create(
            organization=self.org,
            user=self.user2,
            name='page_view',
            timestamp=timezone.make_aware(
                datetime.combine(last_month_end, datetime.min.time())
            )
        )

        # Run task
        result = aggregate_monthly_metrics()

        # Check result
        assert result['status'] == 'success'
        assert str(last_month_end.year) in result['message']
        assert f"{last_month_end.month:02d}" in result['message']

        # Check that metrics were created
        metric = MonthlyMetric.objects.get(
            organization=self.org,
            year=last_month_end.year,
            month=last_month_end.month
        )
        assert metric.mau == 2  # Two distinct users

    def test_aggregate_monthly_metrics_no_events(self):
        """Test that task handles organizations with no events."""
        # Run task without creating any events
        result = aggregate_monthly_metrics()

        # Task should still succeed
        assert result['status'] == 'success'

        # Get last month's date
        today = timezone.now().date()
        first_day = today.replace(day=1)
        last_month_end = first_day - timedelta(days=1)

        # Check that metrics were created with zero values
        metric = MonthlyMetric.objects.get(
            organization=self.org,
            year=last_month_end.year,
            month=last_month_end.month
        )
        assert metric.mau == 0
        assert metric.mrr_cents == 0

    def test_aggregate_monthly_metrics_calculates_mrr_from_daily(self):
        """Test that MRR is calculated from daily metrics."""
        # Get last month's date
        today = timezone.now().date()
        first_day = today.replace(day=1)
        last_month_end = first_day - timedelta(days=1)

        # Create daily metrics for last month
        DailyMetric.objects.create(
            organization=self.org,
            date=last_month_end,
            dau=10,
            new_users=2,
            revenue_cents=5000
        )
        DailyMetric.objects.create(
            organization=self.org,
            date=last_month_end - timedelta(days=1),
            dau=8,
            new_users=1,
            revenue_cents=3000
        )

        # Run task
        aggregate_monthly_metrics()

        # Check that MRR was calculated
        metric = MonthlyMetric.objects.get(
            organization=self.org,
            year=last_month_end.year,
            month=last_month_end.month
        )
        assert metric.mrr_cents == 8000  # 5000 + 3000

    def test_aggregate_monthly_metrics_updates_existing(self):
        """Test that task updates existing metrics."""
        # Get last month's date
        today = timezone.now().date()
        first_day = today.replace(day=1)
        last_month_end = first_day - timedelta(days=1)

        # Create initial metric
        MonthlyMetric.objects.create(
            organization=self.org,
            year=last_month_end.year,
            month=last_month_end.month,
            mau=100,
            mrr_cents=50000
        )

        # Run task
        aggregate_monthly_metrics()

        # Check that only one metric exists
        metrics = MonthlyMetric.objects.filter(
            organization=self.org,
            year=last_month_end.year,
            month=last_month_end.month
        )
        assert metrics.count() == 1

    @patch('analytics.tasks.aggregate_monthly_metrics.retry')
    def test_aggregate_monthly_metrics_retry_on_error(self, mock_retry):
        """Test that task retries on exception."""
        mock_retry.side_effect = Exception('Retry triggered')

        # Patch Organization.objects.all() to raise an exception
        with patch(
            'analytics.tasks.Organization.objects.all',
            side_effect=Exception('Database error')
            ):
            with pytest.raises(Exception):
                aggregate_monthly_metrics()

            # Verify retry was called
            assert mock_retry.called


@pytest.mark.django_db
class TestAggregateFeatureMetricsTask:
    """Test aggregate_feature_metrics Celery task."""

    def setup_method(self):
        """Set up test data."""
        # Create users
        self.user1 = User.objects.create_user(
            email='user1@example.com',
            password='pass123'
        )
        self.user2 = User.objects.create_user(
            email='user2@example.com',
            password='pass123'
        )

        # Create organization
        self.org = Organization.objects.create(
            name='TestOrg',
            owner=self.user1
        )

    def test_aggregate_feature_metrics_success(self):
        """Test successful feature metrics aggregation."""
        yesterday = timezone.now().date() - timedelta(days=1)

        # Create events with feature names
        Event.objects.create(
            organization=self.org,
            user=self.user1,
            name='feature_usage',
            timestamp=timezone.make_aware(
                datetime.combine(yesterday, datetime.min.time())
            ),
            properties={'feature_name': 'search'}
        )
        Event.objects.create(
            organization=self.org,
            user=self.user2,
            name='feature_usage',
            timestamp=timezone.make_aware(
                datetime.combine(yesterday, datetime.min.time())
            ),
            properties={'feature_name': 'search'}
        )
        Event.objects.create(
            organization=self.org,
            user=self.user1,
            name='feature_usage',
            timestamp=timezone.make_aware(
                datetime.combine(yesterday, datetime.min.time())
            ),
            properties={'feature_name': 'export'}
        )

        # Run task
        result = aggregate_feature_metrics()

        # Check result
        assert result['status'] == 'success'
        assert str(yesterday) in result['message']

        # Check that metrics were created
        search_metric = FeatureMetric.objects.get(
            organization=self.org,
            feature_name='search',
            date=yesterday
        )
        assert search_metric.usage_count == 2
        assert search_metric.unique_users == 2

        export_metric = FeatureMetric.objects.get(
            organization=self.org,
            feature_name='export',
            date=yesterday
        )
        assert export_metric.usage_count == 1
        assert export_metric.unique_users == 1

    def test_aggregate_feature_metrics_no_feature_events(self):
        """Test that task handles events without feature_name property."""
        yesterday = timezone.now().date() - timedelta(days=1)

        # Create events without feature_name
        Event.objects.create(
            organization=self.org,
            user=self.user1,
            name='login',
            timestamp=timezone.make_aware(
                datetime.combine(yesterday, datetime.min.time())
            ),
            properties={'ip': '127.0.0.1'}
        )

        # Run task
        result = aggregate_feature_metrics()

        # Task should still succeed
        assert result['status'] == 'success'

        # No feature metrics should be created
        assert FeatureMetric.objects.count() == 0

    def test_aggregate_feature_metrics_multiple_uses_same_user(self):
        """Test that unique_users counts distinct users."""
        yesterday = timezone.now().date() - timedelta(days=1)

        # Create multiple events from same user for same feature
        for i in range(3):
            Event.objects.create(
                organization=self.org,
                user=self.user1,
                name='feature_usage',
                timestamp=timezone.make_aware(
                    datetime.combine(yesterday, datetime.min.time()) + timedelta(hours=i)
                ),
                properties={'feature_name': 'dashboard'}
            )

        # Run task
        aggregate_feature_metrics()

        # Check metrics
        metric = FeatureMetric.objects.get(
            organization=self.org,
            feature_name='dashboard',
            date=yesterday
        )
        assert metric.usage_count == 3
        assert metric.unique_users == 1  # Only one distinct user

    def test_aggregate_feature_metrics_updates_existing(self):
        """Test that task updates existing metrics."""
        yesterday = timezone.now().date() - timedelta(days=1)

        # Create initial metric
        FeatureMetric.objects.create(
            organization=self.org,
            feature_name='search',
            date=yesterday,
            usage_count=100,
            unique_users=50
        )

        # Create event
        Event.objects.create(
            organization=self.org,
            user=self.user1,
            name='feature_usage',
            timestamp=timezone.make_aware(
                datetime.combine(yesterday, datetime.min.time())
            ),
            properties={'feature_name': 'search'}
        )

        # Run task
        aggregate_feature_metrics()

        # Check that only one metric exists and it was updated
        metrics = FeatureMetric.objects.filter(
            organization=self.org,
            feature_name='search',
            date=yesterday
        )
        assert metrics.count() == 1
        assert metrics.first().usage_count == 1  # Updated value

    def test_aggregate_feature_metrics_org_isolation(self):
        """Test that feature metrics are isolated per organization."""
        yesterday = timezone.now().date() - timedelta(days=1)

        # Create another organization
        org2 = Organization.objects.create(
            name='Org2',
            owner=self.user2
        )

        # Create events for both orgs with same feature name
        Event.objects.create(
            organization=self.org,
            user=self.user1,
            name='feature_usage',
            timestamp=timezone.make_aware(
                datetime.combine(yesterday, datetime.min.time())
            ),
            properties={'feature_name': 'search'}
        )
        Event.objects.create(
            organization=org2,
            user=self.user2,
            name='feature_usage',
            timestamp=timezone.make_aware(
                datetime.combine(yesterday, datetime.min.time())
            ),
            properties={'feature_name': 'search'}
        )

        # Run task
        aggregate_feature_metrics()

        # Check that metrics are separate
        metric1 = FeatureMetric.objects.get(
            organization=self.org,
            feature_name='search',
            date=yesterday
        )
        metric2 = FeatureMetric.objects.get(
            organization=org2,
            feature_name='search',
            date=yesterday
        )

        assert metric1.usage_count == 1
        assert metric2.usage_count == 1
        assert metric1.id != metric2.id

    @patch('analytics.tasks.aggregate_feature_metrics.retry')
    def test_aggregate_feature_metrics_retry_on_error(self, mock_retry):
        """Test that task retries on exception."""
        mock_retry.side_effect = Exception('Retry triggered')

        # Patch Organization.objects.all() to raise an exception
        with patch('analytics.tasks.Organization.objects.all', side_effect=Exception('Database error')):
            with pytest.raises(Exception):
                aggregate_feature_metrics()

            # Verify retry was called
            assert mock_retry.called


@pytest.mark.django_db
class TestTasksEdgeCases:
    """Test edge cases for all analytics tasks."""

    def setup_method(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email='user@example.com',
            password='pass123'
        )
        self.org = Organization.objects.create(
            name='TestOrg',
            owner=self.user
        )

    def test_tasks_handle_empty_database(self):
        """Test that tasks handle empty database gracefully."""
        # Delete all organizations
        Organization.objects.all().delete()

        # Run all tasks
        result1 = aggregate_daily_metrics()
        result2 = aggregate_monthly_metrics()
        result3 = aggregate_feature_metrics()

        # All should succeed
        assert result1['status'] == 'success'
        assert result2['status'] == 'success'
        assert result3['status'] == 'success'

    def test_tasks_handle_deleted_users(self):
        """Test that tasks handle events with deleted users."""
        yesterday = timezone.now().date() - timedelta(days=1)

        # Create a separate user for the event (not the org owner)
        event_user = User.objects.create_user(
            email='eventuser@example.com',
            password='pass123'
        )

        # Create event
        Event.objects.create(
            organization=self.org,
            user=event_user,
            name='login',
            timestamp=timezone.make_aware(
                datetime.combine(yesterday, datetime.min.time())
            )
        )

        # Delete user (event.user becomes NULL due to SET_NULL)
        event_user.delete()

        # Run task - should not crash
        result = aggregate_daily_metrics()
        assert result['status'] == 'success'

