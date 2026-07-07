"""
Serializers for feature flag models.
"""

from rest_framework import serializers

from .models import FeatureFlag


class FeatureFlagSerializer(serializers.ModelSerializer):
    """
    Serializer for feature flag data retrieval.
    Includes all fields with proper read-only fields.
    """

    organization_name = serializers.SerializerMethodField()
    is_global = serializers.SerializerMethodField()

    class Meta:
        model = FeatureFlag
        fields = [
            "id",
            "key",
            "name",
            "description",
            "default_enabled",
            "organization",
            "organization_name",
            "enabled",
            "rules",
            "is_global",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "key", "created_at", "updated_at"]

    def get_organization_name(self, obj):
        """Return organization name if exists, otherwise 'Global'"""
        return obj.organization.name if obj.organization else "Global"

    def get_is_global(self, obj):
        """Check if this is a global feature flag"""
        return obj.is_global()

    def to_representation(self, instance):
        """Customize representation to handle organization field"""
        data = super().to_representation(instance)
        # Convert organization to string ID if it exists
        if instance.organization:
            data["organization"] = str(instance.organization.id)
        else:
            data["organization"] = None
        return data


class UpdateFeatureFlagSerializer(serializers.ModelSerializer):
    """
    Serializer for updating feature flag properties.
    Allows updating: name, description, default_enabled, enabled, and rules.
    Does not allow changing key or organization.
    """

    class Meta:
        model = FeatureFlag
        fields = [
            "name",
            "description",
            "default_enabled",
            "enabled",
            "rules",
        ]

    def validate_rules(self, value):
        """Validate that rules is a dictionary"""
        if value is not None and not isinstance(value, dict):
            raise serializers.ValidationError("Rules must be a dictionary/JSON object")
        return value

    def validate(self, attrs):
        """Additional validation for feature flag updates"""
        # Validate rollout_percentage if present in rules
        rules = attrs.get("rules", {})
        if isinstance(rules, dict) and "rollout_percentage" in rules:
            rollout_percentage = rules.get("rollout_percentage")
            if not isinstance(rollout_percentage, (int, float)):
                raise serializers.ValidationError(
                    {"rules": "rollout_percentage must be a number"}
                )
            if not 0 <= rollout_percentage <= 100:
                raise serializers.ValidationError(
                    {"rules": "rollout_percentage must be between 0 and 100"}
                )

        # Validate whitelist if present in rules
        if isinstance(rules, dict) and "whitelist" in rules:
            whitelist = rules.get("whitelist")
            if not isinstance(whitelist, list):
                raise serializers.ValidationError(
                    {"rules": "whitelist must be a list of user IDs"}
                )
            # Ensure all items in whitelist are integers (user IDs)
            if not all(isinstance(item, int) for item in whitelist):
                raise serializers.ValidationError(
                    {"rules": "whitelist must contain only integer user IDs"}
                )

        return attrs
