"""
Tests for analytics serializers.

Tests cover:
- EventSerializer validation and fields
- TrackEventSerializer validation and creation
- DailyMetricSerializer read-only behavior
- MonthlyMetricSerializer read-only behavior
- FeatureMetricSerializer read-only behavior
- Edge cases and invalid data handling
"""
import pytest
from datetime import timedelta
from django.utils import timezone

from accounts.models import User
from organizations.models import Organization
from analytics.models import Event, DailyMetric, MonthlyMetric, FeatureMetric
from analytics.serializers import (
    EventSerializer,
    TrackEventSerializer,
    DailyMetricSerializer,
    MonthlyMetricSerializer,
    FeatureMetricSerializer
)


@pytest.mark.django_db
class TestEventSerializer:
    """Test EventSerializer."""

    def setup_method(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        self.org = Organization.objects.create(
            name='TestOrg',
            owner=self.user
        )
        self.event = Event.objects.create(
            organization=self.org,
            user=self.user,
            name='login',
            timestamp=timezone.now(),
            properties={'ip': '127.0.0.1'}
        )

    def test_event_serializer_fields(self):
        """Test that EventSerializer contains correct fields."""
        serializer = EventSerializer(self.event)
        data = serializer.data

        assert 'id' in data
        assert 'organization' in data
        assert 'name' in data
        assert 'user' in data
        assert 'timestamp' in data
        assert 'properties' in data

        # Fields that should NOT be exposed
        assert 'ip_address' not in data
        assert 'user_agent' not in data
        assert 'received_at' not in data

    def test_event_serializer_read_only_fields(self):
        """Test that id and timestamp are read-only."""
        serializer = EventSerializer(self.event)

        assert 'id' in serializer.Meta.read_only_fields
        assert 'timestamp' in serializer.Meta.read_only_fields

    def test_event_serializer_data_types(self):
        """Test that serialized data has correct types."""
        serializer = EventSerializer(self.event)
        data = serializer.data

        assert isinstance(data['id'], str)  # UUID as string
        assert isinstance(data['name'], str)
        assert isinstance(data['properties'], dict)
        assert isinstance(data['organization'], str)


@pytest.mark.django_db
class TestTrackEventSerializer:
    """Test TrackEventSerializer."""

    def setup_method(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        self.org = Organization.objects.create(
            name='TestOrg',
            owner=self.user
        )

    def test_track_event_serializer_valid_data(self):
        """Test creating event with valid data."""
        data = {
            'organization': self.org.id,
            'user': self.user.id,
            'name': 'page_view',
            'properties': {'page': '/dashboard'},
            'timestamp': timezone.now()
        }

        serializer = TrackEventSerializer(data=data)
        assert serializer.is_valid()

        event = serializer.save()

        assert event.organization == self.org
        assert event.user == self.user
        assert event.name == 'page_view'
        assert event.properties['page'] == '/dashboard'

    def test_track_event_serializer_without_user(self):
        """Test creating event without user (anonymous)."""
        data = {
            'organization': self.org.id,
            'name': 'anonymous_visit',
            'properties': {},
            'timestamp': timezone.now()
        }

        serializer = TrackEventSerializer(data=data)
        assert serializer.is_valid()

        event = serializer.save()

        assert event.user is None
        assert event.name == 'anonymous_visit'

    def test_track_event_serializer_without_properties(self):
        """Test creating event without properties."""
        data = {
            'organization': self.org.id,
            'user': self.user.id,
            'name': 'simple_event',
            'timestamp': timezone.now()
        }

        serializer = TrackEventSerializer(data=data)
        assert serializer.is_valid()

        event = serializer.save()

        assert event.properties == {}

    def test_track_event_serializer_missing_required_fields(self):
        """Test that missing required fields cause validation error."""
        data = {
            'user': self.user.id,
            'properties': {}
        }

        serializer = TrackEventSerializer(data=data)

        assert not serializer.is_valid()
        assert 'organization' in serializer.errors
        assert 'name' in serializer.errors
        assert 'timestamp' in serializer.errors

    def test_track_event_serializer_invalid_organization(self):
        """Test that invalid organization ID causes validation error."""
        data = {
            'organization': 99999,  # Non-existent
            'user': self.user.id,
            'name': 'test_event',
            'timestamp': timezone.now()
        }

        serializer = TrackEventSerializer(data=data)

        assert not serializer.is_valid()
        assert 'organization' in serializer.errors

    def test_track_event_serializer_invalid_user(self):
        """Test that invalid user ID causes validation error."""
        data = {
            'organization': self.org.id,
            'user': 99999,  # Non-existent
            'name': 'test_event',
            'timestamp': timezone.now()
        }

        serializer = TrackEventSerializer(data=data)

        assert not serializer.is_valid()
        assert 'user' in serializer.errors

    def test_track_event_serializer_empty_name(self):
        """Test that empty name causes validation error."""
        data = {
            'organization': self.org.id,
            'user': self.user.id,
            'name': '',
            'timestamp': timezone.now()
        }

        serializer = TrackEventSerializer(data=data)

        assert not serializer.is_valid()
        assert 'name' in serializer.errors

    def test_track_event_serializer_complex_properties(self):
        """Test that complex JSON properties are handled correctly."""
        data = {
            'organization': self.org.id,
            'user': self.user.id,
            'name': 'complex_event',
            'properties': {
                'nested': {
                    'key': 'value',
                    'list': [1, 2, 3]
                },
                'boolean': True,
                'number': 42
            },
            'timestamp': timezone.now()
        }

        serializer = TrackEventSerializer(data=data)
        assert serializer.is_valid()

        event = serializer.save()

        assert event.properties['nested']['key'] == 'value'
        assert event.properties['nested']['list'] == [1, 2, 3]
        assert event.properties['boolean'] is True
        assert event.properties['number'] == 42


@pytest.mark.django_db
class TestDailyMetricSerializer:
    """Test DailyMetricSerializer."""

    def setup_method(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        self.org = Organization.objects.create(
            name='TestOrg',
            owner=self.user
        )
        self.metric = DailyMetric.objects.create(
            organization=self.org,
            date=timezone.now().date(),
            dau=100,
            new_users=10,
            revenue_cents=5000
        )

    def test_daily_metric_serializer_fields(self):
        """Test that DailyMetricSerializer contains correct fields."""
        serializer = DailyMetricSerializer(self.metric)
        data = serializer.data

        assert 'organization' in data
        assert 'date' in data
        assert 'dau' in data
        assert 'new_users' in data
        assert 'revenue_cents' in data

    def test_daily_metric_serializer_all_fields_read_only(self):
        """Test that all fields are read-only."""
        serializer = DailyMetricSerializer(self.metric)

        # All fields should be in read_only_fields
        assert set(serializer.Meta.fields) == set(serializer.Meta.read_only_fields)

    def test_daily_metric_serializer_data_types(self):
        """Test that serialized data has correct types."""
        serializer = DailyMetricSerializer(self.metric)
        data = serializer.data

        assert isinstance(data['organization'], str)
        assert isinstance(data['dau'], int)
        assert isinstance(data['new_users'], int)
        assert isinstance(data['revenue_cents'], int)

    def test_daily_metric_serializer_multiple_instances(self):
        """Test serializing multiple metrics."""
        # Create another metric
        DailyMetric.objects.create(
            organization=self.org,
            date=timezone.now().date() - timedelta(days=1),
            dau=90,
            new_users=8,
            revenue_cents=4500
        )

        metrics = DailyMetric.objects.filter(organization=self.org)
        serializer = DailyMetricSerializer(metrics, many=True)

        assert len(serializer.data) == 2


@pytest.mark.django_db
class TestMonthlyMetricSerializer:
    """Test MonthlyMetricSerializer."""

    def setup_method(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        self.org = Organization.objects.create(
            name='TestOrg',
            owner=self.user
        )
        self.metric = MonthlyMetric.objects.create(
            organization=self.org,
            year=2025,
            month=11,
            mau=500,
            mrr_cents=50000,
            churn_rate=0.05
        )

    def test_monthly_metric_serializer_fields(self):
        """Test that MonthlyMetricSerializer contains correct fields."""
        serializer = MonthlyMetricSerializer(self.metric)
        data = serializer.data

        assert 'organization' in data
        assert 'year' in data
        assert 'month' in data
        assert 'mau' in data
        assert 'mrr_cents' in data
        assert 'churn_rate' in data

    def test_monthly_metric_serializer_all_fields_read_only(self):
        """Test that all fields are read-only."""
        serializer = MonthlyMetricSerializer(self.metric)

        # All fields should be in read_only_fields
        assert set(serializer.Meta.fields) == set(serializer.Meta.read_only_fields)

    def test_monthly_metric_serializer_data_types(self):
        """Test that serialized data has correct types."""
        serializer = MonthlyMetricSerializer(self.metric)
        data = serializer.data

        assert isinstance(data['organization'], str)
        assert isinstance(data['year'], int)
        assert isinstance(data['month'], int)
        assert isinstance(data['mau'], int)
        assert isinstance(data['mrr_cents'], int)
        assert isinstance(data['churn_rate'], float)

    def test_monthly_metric_serializer_null_churn_rate(self):
        """Test serializing metric with null churn_rate."""
        metric = MonthlyMetric.objects.create(
            organization=self.org,
            year=2025,
            month=10,
            mau=450,
            mrr_cents=45000,
            churn_rate=None
        )

        serializer = MonthlyMetricSerializer(metric)
        data = serializer.data

        assert data['churn_rate'] is None


@pytest.mark.django_db
class TestFeatureMetricSerializer:
    """Test FeatureMetricSerializer."""

    def setup_method(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        self.org = Organization.objects.create(
            name='TestOrg',
            owner=self.user
        )
        self.metric = FeatureMetric.objects.create(
            organization=self.org,
            feature_name='search',
            date=timezone.now().date(),
            usage_count=150,
            unique_users=50,
            last_used_at=timezone.now()
        )

    def test_feature_metric_serializer_fields(self):
        """Test that FeatureMetricSerializer contains correct fields."""
        serializer = FeatureMetricSerializer(self.metric)
        data = serializer.data

        assert 'organization' in data
        assert 'feature_name' in data
        assert 'date' in data
        assert 'usage_count' in data
        assert 'unique_users' in data
        assert 'last_used_at' in data

    def test_feature_metric_serializer_all_fields_read_only(self):
        """Test that all fields are read-only."""
        serializer = FeatureMetricSerializer(self.metric)

        # All fields should be in read_only_fields
        assert set(serializer.Meta.fields) == set(serializer.Meta.read_only_fields)

    def test_feature_metric_serializer_data_types(self):
        """Test that serialized data has correct types."""
        serializer = FeatureMetricSerializer(self.metric)
        data = serializer.data

        assert isinstance(data['organization'], str)
        assert isinstance(data['feature_name'], str)
        assert isinstance(data['usage_count'], int)
        assert isinstance(data['unique_users'], int)

    def test_feature_metric_serializer_null_last_used_at(self):
        """Test serializing metric with null last_used_at."""
        metric = FeatureMetric.objects.create(
            organization=self.org,
            feature_name='export',
            date=timezone.now().date(),
            usage_count=10,
            unique_users=5,
            last_used_at=None
        )

        serializer = FeatureMetricSerializer(metric)
        data = serializer.data

        assert data['last_used_at'] is None


@pytest.mark.django_db
class TestSerializersEdgeCases:
    """Test edge cases for all analytics serializers."""

    def setup_method(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        self.org = Organization.objects.create(
            name='TestOrg',
            owner=self.user
        )

    def test_track_event_very_long_name(self):
        """Test that very long event names are handled."""
        data = {
            'organization': self.org.id,
            'user': self.user.id,
            'name': 'x' * 201,  # Exceeds max_length of 200
            'timestamp': timezone.now()
        }

        serializer = TrackEventSerializer(data=data)

        # Should fail validation
        assert not serializer.is_valid()
        assert 'name' in serializer.errors

    def test_track_event_max_length_name(self):
        """Test that max length event names are accepted."""
        data = {
            'organization': self.org.id,
            'user': self.user.id,
            'name': 'x' * 200,  # Exactly max_length
            'timestamp': timezone.now()
        }

        serializer = TrackEventSerializer(data=data)

        assert serializer.is_valid()

    def test_track_event_future_timestamp(self):
        """Test that future timestamps are accepted."""
        future_time = timezone.now() + timedelta(days=1)

        data = {
            'organization': self.org.id,
            'user': self.user.id,
            'name': 'future_event',
            'timestamp': future_time
        }

        serializer = TrackEventSerializer(data=data)

        # Should be valid (system doesn't restrict future timestamps)
        assert serializer.is_valid()

    def test_track_event_very_old_timestamp(self):
        """Test that very old timestamps are accepted."""
        old_time = timezone.now() - timedelta(days=365*10)  # 10 years ago

        data = {
            'organization': self.org.id,
            'user': self.user.id,
            'name': 'old_event',
            'timestamp': old_time
        }

        serializer = TrackEventSerializer(data=data)

        assert serializer.is_valid()

    def test_event_serializer_with_empty_properties(self):
        """Test serializing event with empty properties."""
        event = Event.objects.create(
            organization=self.org,
            user=self.user,
            name='empty_props',
            timestamp=timezone.now(),
            properties={}
        )

        serializer = EventSerializer(event)
        data = serializer.data

        assert data['properties'] == {}

    def test_daily_metric_zero_values(self):
        """Test serializing daily metric with all zero values."""
        metric = DailyMetric.objects.create(
            organization=self.org,
            date=timezone.now().date(),
            dau=0,
            new_users=0,
            revenue_cents=0
        )

        serializer = DailyMetricSerializer(metric)
        data = serializer.data

        assert data['dau'] == 0
        assert data['new_users'] == 0
        assert data['revenue_cents'] == 0

    def test_daily_metric_large_values(self):
        """Test serializing daily metric with very large values."""
        metric = DailyMetric.objects.create(
            organization=self.org,
            date=timezone.now().date(),
            dau=1000000,
            new_users=100000,
            revenue_cents=9999999999999  # Very large number
        )

        serializer = DailyMetricSerializer(metric)
        data = serializer.data

        assert data['dau'] == 1000000
        assert data['new_users'] == 100000
        assert data['revenue_cents'] == 9999999999999

    def test_monthly_metric_boundary_months(self):
        """Test serializing monthly metrics for boundary months."""
        # January
        metric1 = MonthlyMetric.objects.create(
            organization=self.org,
            year=2025,
            month=1,
            mau=100,
            mrr_cents=10000
        )

        # December
        metric2 = MonthlyMetric.objects.create(
            organization=self.org,
            year=2025,
            month=12,
            mau=200,
            mrr_cents=20000
        )

        serializer1 = MonthlyMetricSerializer(metric1)
        serializer2 = MonthlyMetricSerializer(metric2)

        assert serializer1.data['month'] == 1
        assert serializer2.data['month'] == 12

    def test_feature_metric_special_characters_in_name(self):
        """Test serializing feature metric with special characters in name."""
        metric = FeatureMetric.objects.create(
            organization=self.org,
            feature_name='feature-with_special.chars@123',
            date=timezone.now().date(),
            usage_count=10,
            unique_users=5
        )

        serializer = FeatureMetricSerializer(metric)
        data = serializer.data

        assert data['feature_name'] == 'feature-with_special.chars@123'

    def test_track_event_unicode_characters(self):
        """Test creating event with unicode characters."""
        data = {
            'organization': self.org.id,
            'user': self.user.id,
            'name': '登录_événement_🎉',
            'properties': {'message': 'Hello 世界 🌍'},
            'timestamp': timezone.now()
        }

        serializer = TrackEventSerializer(data=data)
        assert serializer.is_valid()

        event = serializer.save()

        assert event.name == '登录_événement_🎉'
        assert event.properties['message'] == 'Hello 世界 🌍'

