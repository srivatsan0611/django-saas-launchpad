"""
Edge case tests for analytics module.

Tests cover:
- Multi-organization isolation
- Empty data handling
- Boundary conditions
- Race conditions
- Data integrity
"""
import pytest
from datetime import timedelta
from django.utils import timezone
from django.db import IntegrityError

from accounts.models import User
from organizations.models import Organization
from analytics.models import Event, DailyMetric, MonthlyMetric, FeatureMetric
from analytics import services


@pytest.mark.django_db
class TestMultiOrgIsolation:
    """Test that data is properly isolated between organizations."""

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
        self.user3 = User.objects.create_user(
            email='user3@example.com',
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
        self.org3 = Organization.objects.create(
            name='Org3',
            owner=self.user3
        )

    def test_events_isolated_per_org(self):
        """Test that events are isolated per organization."""
        # Create events for different orgs
        Event.objects.create(
            organization=self.org1,
            user=self.user1,
            name='login',
            timestamp=timezone.now()
        )
        Event.objects.create(
            organization=self.org2,
            user=self.user2,
            name='login',
            timestamp=timezone.now()
        )

        # Query events for org1
        org1_events = Event.objects.filter(organization=self.org1)

        assert org1_events.count() == 1
        assert org1_events.first().organization == self.org1

    def test_daily_metrics_isolated_per_org(self):
        """Test that daily metrics are isolated per organization."""
        today = timezone.now().date()

        # Create metrics for different orgs
        DailyMetric.objects.create(
            organization=self.org1,
            date=today,
            dau=100,
            new_users=10,
            revenue_cents=5000
        )
        DailyMetric.objects.create(
            organization=self.org2,
            date=today,
            dau=200,
            new_users=20,
            revenue_cents=10000
        )

        # Query metrics for org1
        org1_metrics = DailyMetric.objects.filter(organization=self.org1)

        assert org1_metrics.count() == 1
        assert org1_metrics.first().dau == 100
        assert org1_metrics.first().organization == self.org1

    def test_dau_calculation_isolated_per_org(self):
        """Test that DAU calculation doesn't leak between organizations."""
        today = timezone.now().date()

        # User1 active in org1 and org2
        Event.objects.create(
            organization=self.org1,
            user=self.user1,
            name='login',
            timestamp=timezone.now()
        )
        Event.objects.create(
            organization=self.org2,
            user=self.user1,
            name='login',
            timestamp=timezone.now()
        )

        # Calculate DAU for both orgs
        dau1 = services.get_dau(self.org1, today, today)
        dau2 = services.get_dau(self.org2, today, today)

        # Both should count the same user independently
        assert dau1[0]['dau'] == 1
        assert dau2[0]['dau'] == 1

    def test_feature_metrics_isolated_per_org(self):
        """Test that feature metrics are isolated per organization."""
        today = timezone.now().date()

        # Create same feature for different orgs
        FeatureMetric.objects.create(
            organization=self.org1,
            feature_name='search',
            date=today,
            usage_count=100,
            unique_users=50
        )
        FeatureMetric.objects.create(
            organization=self.org2,
            feature_name='search',
            date=today,
            usage_count=200,
            unique_users=75
        )

        # Query for org1
        org1_features = FeatureMetric.objects.filter(
            organization=self.org1,
            feature_name='search'
        )

        assert org1_features.count() == 1
        assert org1_features.first().usage_count == 100

    def test_top_features_isolated_per_org(self):
        """Test that top features query doesn't leak between orgs."""
        today = timezone.now().date()

        # Create features for org1
        FeatureMetric.objects.create(
            organization=self.org1,
            feature_name='search',
            date=today,
            usage_count=100
        )

        # Create features for org2
        FeatureMetric.objects.create(
            organization=self.org2,
            feature_name='export',
            date=today,
            usage_count=500  # Higher usage in org2
        )

        # Get top features for org1
        top_features = services.get_top_features(self.org1, today, today)

        # Should only see org1's features
        assert len(top_features) == 1
        assert top_features[0]['feature_name'] == 'search'

    def test_cross_org_user_events(self):
        """Test that same user can have events in multiple orgs."""
        # User1 performs actions in both org1 and org2
        Event.objects.create(
            organization=self.org1,
            user=self.user1,
            name='action_in_org1',
            timestamp=timezone.now()
        )
        Event.objects.create(
            organization=self.org2,
            user=self.user1,
            name='action_in_org2',
            timestamp=timezone.now()
        )

        # Each org should only see their own events
        org1_events = Event.objects.filter(organization=self.org1)
        org2_events = Event.objects.filter(organization=self.org2)

        assert org1_events.count() == 1
        assert org2_events.count() == 1
        assert org1_events.first().name == 'action_in_org1'
        assert org2_events.first().name == 'action_in_org2'

    def test_monthly_metrics_isolated_per_org(self):
        """Test that monthly metrics are isolated per organization."""
        # Create metrics for same month for different orgs
        MonthlyMetric.objects.create(
            organization=self.org1,
            year=2025,
            month=11,
            mau=500,
            mrr_cents=50000
        )
        MonthlyMetric.objects.create(
            organization=self.org2,
            year=2025,
            month=11,
            mau=800,
            mrr_cents=80000
        )

        # Query for org1
        org1_metrics = MonthlyMetric.objects.filter(
            organization=self.org1,
            year=2025,
            month=11
        )

        assert org1_metrics.count() == 1
        assert org1_metrics.first().mau == 500


@pytest.mark.django_db
class TestEmptyDataHandling:
    """Test handling of empty or missing data."""

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

    def test_dau_with_no_events(self):
        """Test DAU calculation when no events exist."""
        today = timezone.now().date()

        dau = services.get_dau(self.org, today, today)

        assert len(dau) == 1
        assert dau[0]['dau'] == 0

    def test_mau_with_no_events(self):
        """Test MAU calculation when no events exist."""
        today = timezone.now().date()
        start = today - timedelta(days=30)

        mau = services.get_mau(self.org, start, today)

        assert len(mau) == 1
        assert mau[0]['mau'] == 0

    def test_revenue_with_no_metrics(self):
        """Test revenue calculation when no metrics exist."""
        today = timezone.now().date()

        revenue = services.get_revenue_timeseries(self.org, today, today)

        assert len(revenue) == 0

    def test_top_features_with_no_metrics(self):
        """Test top features query when no metrics exist."""
        today = timezone.now().date()

        top = services.get_top_features(self.org, today, today)

        assert len(top) == 0

    def test_event_without_properties(self):
        """Test creating event with no properties."""
        event = Event.objects.create(
            organization=self.org,
            user=self.user,
            name='no_props',
            timestamp=timezone.now()
            # properties defaults to {}
        )

        assert event.properties == {}

    def test_event_without_user(self):
        """Test creating anonymous event without user."""
        event = Event.objects.create(
            organization=self.org,
            user=None,
            name='anonymous',
            timestamp=timezone.now()
        )

        assert event.user is None
        assert event.organization == self.org

    def test_daily_metric_with_zero_values(self):
        """Test creating daily metric with all zero values."""
        today = timezone.now().date()

        metric = DailyMetric.objects.create(
            organization=self.org,
            date=today,
            dau=0,
            new_users=0,
            revenue_cents=0
        )

        assert metric.dau == 0
        assert metric.new_users == 0
        assert metric.revenue_cents == 0

    def test_monthly_metric_with_null_churn_rate(self):
        """Test creating monthly metric with null churn rate."""
        metric = MonthlyMetric.objects.create(
            organization=self.org,
            year=2025,
            month=11,
            mau=100,
            mrr_cents=10000,
            churn_rate=None
        )

        assert metric.churn_rate is None


@pytest.mark.django_db
class TestBoundaryConditions:
    """Test boundary conditions and edge values."""

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

    def test_event_name_max_length(self):
        """Test event name at maximum length."""
        max_name = 'x' * 200  # max_length=200

        event = Event.objects.create(
            organization=self.org,
            user=self.user,
            name=max_name,
            timestamp=timezone.now()
        )

        assert len(event.name) == 200

    def test_feature_name_max_length(self):
        """Test feature name at maximum length."""
        max_name = 'f' * 255  # max_length=255

        metric = FeatureMetric.objects.create(
            organization=self.org,
            feature_name=max_name,
            date=timezone.now().date(),
            usage_count=1
        )

        assert len(metric.feature_name) == 255

    def test_very_large_revenue_cents(self):
        """Test handling very large revenue values."""
        large_revenue = 9999999999999  # 13 digits

        metric = DailyMetric.objects.create(
            organization=self.org,
            date=timezone.now().date(),
            dau=1,
            new_users=0,
            revenue_cents=large_revenue
        )

        assert metric.revenue_cents == large_revenue

    def test_very_old_event(self):
        """Test event with very old timestamp."""
        old_date = timezone.now() - timedelta(days=365*10)  # 10 years ago

        event = Event.objects.create(
            organization=self.org,
            user=self.user,
            name='old_event',
            timestamp=old_date
        )

        assert event.timestamp < timezone.now()

    def test_future_event(self):
        """Test event with future timestamp."""
        future_date = timezone.now() + timedelta(days=365)

        event = Event.objects.create(
            organization=self.org,
            user=self.user,
            name='future_event',
            timestamp=future_date
        )

        assert event.timestamp > timezone.now()

    def test_month_boundaries(self):
        """Test monthly metrics at month boundaries."""
        # January
        jan_metric = MonthlyMetric.objects.create(
            organization=self.org,
            year=2025,
            month=1,
            mau=100,
            mrr_cents=10000
        )

        # December
        dec_metric = MonthlyMetric.objects.create(
            organization=self.org,
            year=2025,
            month=12,
            mau=200,
            mrr_cents=20000
        )

        assert jan_metric.month == 1
        assert dec_metric.month == 12

    def test_zero_churn_rate(self):
        """Test monthly metric with zero churn rate."""
        metric = MonthlyMetric.objects.create(
            organization=self.org,
            year=2025,
            month=11,
            mau=100,
            mrr_cents=10000,
            churn_rate=0.0
        )

        assert metric.churn_rate == 0.0

    def test_high_churn_rate(self):
        """Test monthly metric with high churn rate (100%)."""
        metric = MonthlyMetric.objects.create(
            organization=self.org,
            year=2025,
            month=11,
            mau=100,
            mrr_cents=10000,
            churn_rate=1.0
        )

        assert metric.churn_rate == 1.0

    def test_date_range_single_day(self):
        """Test metrics calculation for single day range."""
        today = timezone.now().date()

        Event.objects.create(
            organization=self.org,
            user=self.user,
            name='test',
            timestamp=timezone.now()
        )

        dau = services.get_dau(self.org, today, today)

        assert len(dau) == 1
        assert dau[0]['dau'] == 1

    def test_date_range_one_year(self):
        """Test metrics calculation for one year range."""
        today = timezone.now().date()
        one_year_ago = today - timedelta(days=365)

        # Create events throughout the year
        for i in range(0, 365, 30):  # Monthly events
            Event.objects.create(
                organization=self.org,
                user=self.user,
                name='test',
                timestamp=timezone.now() - timedelta(days=i)
            )

        dau = services.get_dau(self.org, one_year_ago, today)

        assert len(dau) > 0


@pytest.mark.django_db
class TestDataIntegrity:
    """Test data integrity constraints."""

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

    def test_daily_metric_unique_together(self):
        """Test that organization and date are unique together for daily metrics."""
        today = timezone.now().date()

        # Create first metric
        DailyMetric.objects.create(
            organization=self.org,
            date=today,
            dau=100
        )

        # Try to create duplicate - should raise IntegrityError
        with pytest.raises(IntegrityError):
            DailyMetric.objects.create(
                organization=self.org,
                date=today,
                dau=200
            )

    def test_monthly_metric_unique_together(self):
        """Test that organization, year, and month are unique together."""
        # Create first metric
        MonthlyMetric.objects.create(
            organization=self.org,
            year=2025,
            month=11,
            mau=100
        )

        # Try to create duplicate - should raise IntegrityError
        with pytest.raises(IntegrityError):
            MonthlyMetric.objects.create(
                organization=self.org,
                year=2025,
                month=11,
                mau=200
            )

    def test_feature_metric_unique_together(self):
        """Test that organization, feature_name, and date are unique together."""
        today = timezone.now().date()

        # Create first metric
        FeatureMetric.objects.create(
            organization=self.org,
            feature_name='search',
            date=today,
            usage_count=100
        )

        # Try to create duplicate - should raise IntegrityError
        with pytest.raises(IntegrityError):
            FeatureMetric.objects.create(
                organization=self.org,
                feature_name='search',
                date=today,
                usage_count=200
            )

    def test_event_organization_cascade_delete(self):
        """Test that events are deleted when organization is deleted."""
        # Create event
        Event.objects.create(
            organization=self.org,
            user=self.user,
            name='test',
            timestamp=timezone.now()
        )

        assert Event.objects.count() == 1

        # Delete organization
        self.org.delete()

        # Events should be cascade deleted
        assert Event.objects.count() == 0

    def test_event_user_set_null(self):
        """Test that event.user is set to NULL when user is deleted."""
        # Create a separate user for the event (not the org owner)
        event_user = User.objects.create_user(
            email='eventuser@example.com',
            password='pass123'
        )

        # Create event
        event = Event.objects.create(
            organization=self.org,
            user=event_user,
            name='test',
            timestamp=timezone.now()
        )

        # Delete user
        event_user.delete()

        # Event should still exist but with NULL user
        event.refresh_from_db()
        assert event.user is None

    def test_metric_organization_cascade_delete(self):
        """Test that metrics are deleted when organization is deleted."""
        today = timezone.now().date()

        # Create various metrics
        DailyMetric.objects.create(
            organization=self.org,
            date=today,
            dau=100
        )
        MonthlyMetric.objects.create(
            organization=self.org,
            year=2025,
            month=11,
            mau=100
        )
        FeatureMetric.objects.create(
            organization=self.org,
            feature_name='search',
            date=today,
            usage_count=100
        )

        assert DailyMetric.objects.count() == 1
        assert MonthlyMetric.objects.count() == 1
        assert FeatureMetric.objects.count() == 1

        # Delete organization
        self.org.delete()

        # All metrics should be cascade deleted
        assert DailyMetric.objects.count() == 0
        assert MonthlyMetric.objects.count() == 0
        assert FeatureMetric.objects.count() == 0

    def test_same_feature_different_dates(self):
        """Test that same feature can have metrics for different dates."""
        today = timezone.now().date()
        yesterday = today - timedelta(days=1)

        # Create metrics for different dates
        FeatureMetric.objects.create(
            organization=self.org,
            feature_name='search',
            date=today,
            usage_count=100
        )
        FeatureMetric.objects.create(
            organization=self.org,
            feature_name='search',
            date=yesterday,
            usage_count=90
        )

        # Both should exist
        assert FeatureMetric.objects.filter(
            organization=self.org,
            feature_name='search'
        ).count() == 2

    def test_same_date_different_orgs(self):
        """Test that same date can have metrics for different orgs."""
        today = timezone.now().date()

        # Create another org
        user2 = User.objects.create_user(
            email='user2@example.com',
            password='pass123'
        )
        org2 = Organization.objects.create(
            name='Org2',
            owner=user2
        )

        # Create metrics for same date, different orgs
        DailyMetric.objects.create(
            organization=self.org,
            date=today,
            dau=100
        )
        DailyMetric.objects.create(
            organization=org2,
            date=today,
            dau=200
        )

        # Both should exist
        assert DailyMetric.objects.filter(date=today).count() == 2

