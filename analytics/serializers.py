from rest_framework import serializers
from .models import Event, DailyMetric, FeatureMetric, MonthlyMetric


class EventSerializer(serializers.ModelSerializer):
    """
    Serializer for event model.
    Includes id, organization, name, user, timestamp, properties.
    """
    class Meta:
        model = Event
        fields = [
            'id',
            'organization',
            'name',
            'user',
            'timestamp',
            'properties',
        ]
        read_only_fields = ['id', 'timestamp']


class TrackEventSerializer(serializers.ModelSerializer):
    """
    Serializer for tracking events.
    Includes organization, user, name, properties, and timestamp.
    """
    class Meta:
        model = Event
        fields = [
            'organization',
            'user',
            'name',
            'properties',
            'timestamp',
        ]

    def create(self, validated_data):
        event = Event.objects.create(**validated_data)
        return event


class DailyMetricSerializer(serializers.ModelSerializer):
    """
    Serializer for daily aggregated metrics like DAU, new users, and revenue.
    Includes organization, date, DAU, new users, and revenue data.
    """
    class Meta:
        model = DailyMetric
        fields = [
            'organization',
            'date',
            'dau',
            'new_users',
            'revenue_cents',
        ]
        read_only_fields = fields

class MonthlyMetricSerializer(serializers.ModelSerializer):
    """
    Serializer for monthly aggregated metrics like MAU, MRR, and churn rate.
    Includes organization, year, month, MAU, MRR, and churn rate.
    """
    class Meta:
        model = MonthlyMetric
        fields = [
            'organization',
            'year',
            'month',
            'mau',
            'mrr_cents',
            'churn_rate',
        ]
        read_only_fields = fields


class FeatureMetricSerializer(serializers.ModelSerializer):
    """
    Serializer for feature usage metrics.
    Includes organization, feature_name, date, usage_count, unique_users, and last_used_at.
    """
    class Meta:
        model = FeatureMetric
        fields = [
            'organization',
            'feature_name',
            'date',
            'usage_count',
            'unique_users',
            'last_used_at',
        ]
        read_only_fields = fields