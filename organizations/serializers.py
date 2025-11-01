from rest_framework import serializers
from django.utils import timezone
from datetime import timedelta
from .models import Organization, Membership, Invitation
from accounts.models import User


class UserBasicSerializer(serializers.ModelSerializer):
    """Basic user info for nested serialization"""
    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name']
        read_only_fields = ['id', 'email', 'first_name', 'last_name']


class OrganizationSerializer(serializers.ModelSerializer):
    """
    Serializer for retrieving organization data.
    Includes owner details and member count.
    """
    owner = UserBasicSerializer(read_only=True)
    member_count = serializers.SerializerMethodField()

    class Meta:
        model = Organization
        fields = [
            'id',
            'name',
            'slug',
            'owner',
            'member_count',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'slug', 'created_at', 'updated_at']

    def get_member_count(self, obj):
        """Returns the total number of members in the organization"""
        return obj.get_member_count()


class MembershipSerializer(serializers.ModelSerializer):
    """
    Serializer for membership data.
    Includes user and organization details.
    """
    user = UserBasicSerializer(read_only=True)
    organization = serializers.StringRelatedField(read_only=True)
    organization_id = serializers.UUIDField(source='organization.id', read_only=True)

    class Meta:
        model = Membership
        fields = [
            'id',
            'user',
            'organization',
            'organization_id',
            'role',
            'joined_at'
        ]
        read_only_fields = ['id', 'joined_at']


class InvitationSerializer(serializers.ModelSerializer):
    """
    Serializer for invitation data.
    Includes computed fields for status checks.
    """
    invited_by = UserBasicSerializer(read_only=True)
    organization = OrganizationSerializer(read_only=True)
    is_expired = serializers.SerializerMethodField()
    is_accepted = serializers.SerializerMethodField()
    can_accept = serializers.SerializerMethodField()

    class Meta:
        model = Invitation
        fields = [
            'id',
            'email',
            'organization',
            'invited_by',
            'role',
            'token',
            'expires_at',
            'accepted_at',
            'created_at',
            'is_expired',
            'is_accepted',
            'can_accept'
        ]
        read_only_fields = [
            'id',
            'token',
            'expires_at',
            'accepted_at',
            'created_at'
        ]

    def get_is_expired(self, obj):
        """Check if invitation has expired"""
        return obj.is_expired()

    def get_is_accepted(self, obj):
        """Check if invitation has been accepted"""
        return obj.is_accepted()

    def get_can_accept(self, obj):
        """Check if invitation can still be accepted"""
        return obj.can_accept()


class CreateOrganizationSerializer(serializers.ModelSerializer):
    """
    Serializer for creating a new organization.
    Only requires name - slug is auto-generated and current user becomes owner.
    """
    class Meta:
        model = Organization
        fields = ['name']

    def create(self, validated_data):
        """
        Create organization with current user as owner.
        Auto-generates slug from name.
        """
        request = self.context.get('request')
        if not request or not request.user:
            raise serializers.ValidationError("User must be authenticated")

        # Create organization with current user as owner
        organization = Organization.objects.create(
            name=validated_data['name'],
            owner=request.user
        )

        return organization


class CreateInvitationSerializer(serializers.ModelSerializer):
    """
    Serializer for creating a new invitation.
    Validates that email is not already a member or has pending invitation.
    """
    organization_id = serializers.UUIDField(write_only=True)

    class Meta:
        model = Invitation
        fields = ['email', 'organization_id', 'role']

    def validate_email(self, value):
        """Ensure email is valid"""
        return value.lower()

    def validate(self, attrs):
        """
        Validate that:
        1. User is not already a member of the organization
        2. No pending invitation exists for this email in this organization
        """
        email = attrs['email']
        organization_id = attrs['organization_id']

        try:
            organization = Organization.objects.get(id=organization_id)
        except Organization.DoesNotExist:
            raise serializers.ValidationError({
                'organization_id': 'Organization not found'
            })

        # Check if user is already a member
        existing_user = User.objects.filter(email=email).first()
        if existing_user:
            if Membership.objects.filter(
                user=existing_user,
                organization=organization
            ).exists():
                raise serializers.ValidationError({
                    'email': 'This user is already a member of the organization'
                })

        # Check if there's already a pending invitation
        existing_invitation = Invitation.objects.filter(
            email=email,
            organization=organization,
            accepted_at__isnull=True
        ).first()

        if existing_invitation:
            if existing_invitation.can_accept():
                raise serializers.ValidationError({
                    'email': 'A pending invitation already exists for this email'
                })
            else:
                # Delete expired invitation
                existing_invitation.delete()

        attrs['organization'] = organization
        return attrs

    def create(self, validated_data):
        """
        Create invitation with current user as inviter.
        Sets expiry to 7 days from now and triggers invitation email.
        """
        request = self.context.get('request')
        if not request or not request.user:
            raise serializers.ValidationError("User must be authenticated")

        # Remove organization_id from validated_data (we added organization object)
        organization_id = validated_data.pop('organization_id', None)
        organization = validated_data.get('organization')

        invitation = Invitation.objects.create(
            email=validated_data['email'],
            organization=organization,
            invited_by=request.user,
            role=validated_data.get('role', 'member'),
            expires_at=timezone.now() + timedelta(days=7)
        )

        # Trigger async email task
        from organizations.tasks import send_invitation_email
        send_invitation_email.delay(str(invitation.id))

        return invitation


class UpdateMembershipSerializer(serializers.ModelSerializer):
    """
    Serializer for updating membership role.
    Only allows role updates, not user or organization changes.
    """
    class Meta:
        model = Membership
        fields = ['role']

    def validate_role(self, value):
        """Ensure role is valid"""
        if value not in dict(Membership.ROLE_CHOICES):
            raise serializers.ValidationError("Invalid role")
        return value
