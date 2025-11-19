"""
Tests for Organization serializers.

Tests cover:
- Serializer validation
- Required fields
- Read-only fields
- Custom validation logic
- Serializer creation and updates
"""

import pytest
from django.utils import timezone
from datetime import timedelta
from rest_framework.test import APIRequestFactory
from rest_framework.request import Request

from accounts.models import User
from organizations.models import Organization, Membership, Invitation
from organizations.serializers import (
    OrganizationSerializer,
    CreateOrganizationSerializer,
    MembershipSerializer,
    UpdateMembershipSerializer,
    InvitationSerializer,
    CreateInvitationSerializer,
)


@pytest.mark.django_db
class TestOrganizationSerializer:
    """Tests for OrganizationSerializer"""

    def test_serialize_organization(self):
        """Test serializing an organization"""
        owner = User.objects.create_user(
            email='owner@example.com',
            password='testpass123'
        )
        org = Organization.objects.create(
            name='Test Org',
            owner=owner
        )

        serializer = OrganizationSerializer(org)
        data = serializer.data

        assert data['name'] == 'Test Org'
        assert data['slug'] == 'test-org'
        assert data['owner']['email'] == 'owner@example.com'
        assert data['member_count'] == 1
        assert 'created_at' in data
        assert 'updated_at' in data

    def test_read_only_fields(self):
        """Test that certain fields are read-only"""
        owner = User.objects.create_user(
            email='owner@example.com',
            password='testpass123'
        )
        org = Organization.objects.create(
            name='Test Org',
            owner=owner
        )

        serializer = OrganizationSerializer(org, data={'name': 'Test Org', 'slug': 'new-slug'}, partial=True)
        assert serializer.is_valid()
        serializer.save()

        org.refresh_from_db()
        assert org.slug == 'test-org'  # Slug should not change


@pytest.mark.django_db
class TestCreateOrganizationSerializer:
    """Tests for CreateOrganizationSerializer"""

    def test_create_organization(self):
        """Test creating an organization"""
        user = User.objects.create_user(
            email='owner@example.com',
            password='testpass123'
        )

        # Create mock request
        factory = APIRequestFactory()
        request = factory.post('/fake-url/')
        request.user = user

        serializer = CreateOrganizationSerializer(
            data={'name': 'New Org'},
            context={'request': Request(request)}
        )

        assert serializer.is_valid()
        org = serializer.save()

        assert org.name == 'New Org'
        assert org.owner == user
        assert org.slug == 'new-org'

    def test_create_without_name(self):
        """Test that name is required"""
        user = User.objects.create_user(
            email='owner@example.com',
            password='testpass123'
        )

        factory = APIRequestFactory()
        request = factory.post('/fake-url/')
        request.user = user

        serializer = CreateOrganizationSerializer(
            data={},
            context={'request': Request(request)}
        )

        assert not serializer.is_valid()
        assert 'name' in serializer.errors


@pytest.mark.django_db
class TestMembershipSerializer:
    """Tests for MembershipSerializer"""

    def test_serialize_membership(self):
        """Test serializing a membership"""
        owner = User.objects.create_user(
            email='owner@example.com',
            password='testpass123'
        )
        user = User.objects.create_user(
            email='member@example.com',
            password='testpass123',
            first_name='John',
            last_name='Doe'
        )
        org = Organization.objects.create(
            name='Test Org',
            owner=owner
        )
        membership = Membership.objects.create(
            user=user,
            organization=org,
            role='member'
        )

        serializer = MembershipSerializer(membership)
        data = serializer.data

        assert data['user']['email'] == 'member@example.com'
        assert data['user']['first_name'] == 'John'
        assert data['user']['last_name'] == 'Doe'
        assert data['organization'] == 'Test Org'
        assert data['role'] == 'member'
        assert 'joined_at' in data


@pytest.mark.django_db
class TestUpdateMembershipSerializer:
    """Tests for UpdateMembershipSerializer"""

    def test_update_role(self):
        """Test updating membership role"""
        owner = User.objects.create_user(
            email='owner@example.com',
            password='testpass123'
        )
        user = User.objects.create_user(
            email='member@example.com',
            password='testpass123'
        )
        org = Organization.objects.create(
            name='Test Org',
            owner=owner
        )
        membership = Membership.objects.create(
            user=user,
            organization=org,
            role='member'
        )

        serializer = UpdateMembershipSerializer(
            membership,
            data={'role': 'admin'},
            partial=True
        )

        assert serializer.is_valid()
        serializer.save()

        membership.refresh_from_db()
        assert membership.role == 'admin'

    def test_invalid_role(self):
        """Test that invalid role is rejected"""
        owner = User.objects.create_user(
            email='owner@example.com',
            password='testpass123'
        )
        user = User.objects.create_user(
            email='member@example.com',
            password='testpass123'
        )
        org = Organization.objects.create(
            name='Test Org',
            owner=owner
        )
        membership = Membership.objects.create(
            user=user,
            organization=org,
            role='member'
        )

        serializer = UpdateMembershipSerializer(
            membership,
            data={'role': 'invalid_role'},
            partial=True
        )

        assert not serializer.is_valid()
        assert 'role' in serializer.errors


@pytest.mark.django_db
class TestInvitationSerializer:
    """Tests for InvitationSerializer"""

    def test_serialize_invitation(self):
        """Test serializing an invitation"""
        owner = User.objects.create_user(
            email='owner@example.com',
            password='testpass123'
        )
        org = Organization.objects.create(
            name='Test Org',
            owner=owner
        )
        invitation = Invitation.objects.create(
            email='invitee@example.com',
            organization=org,
            invited_by=owner,
            role='member'
        )

        serializer = InvitationSerializer(invitation)
        data = serializer.data

        assert data['email'] == 'invitee@example.com'
        assert data['organization']['name'] == 'Test Org'
        assert data['invited_by']['email'] == 'owner@example.com'
        assert data['role'] == 'member'
        assert data['is_expired'] is False
        assert data['is_accepted'] is False
        assert data['can_accept'] is True
        assert 'token' in data
        assert 'expires_at' in data


@pytest.mark.django_db
class TestCreateInvitationSerializer:
    """Tests for CreateInvitationSerializer"""

    def test_create_invitation(self):
        """Test creating an invitation"""
        owner = User.objects.create_user(
            email='owner@example.com',
            password='testpass123'
        )
        org = Organization.objects.create(
            name='Test Org',
            owner=owner
        )

        factory = APIRequestFactory()
        request = factory.post('/fake-url/')
        request.user = owner

        serializer = CreateInvitationSerializer(
            data={
                'email': 'invitee@example.com',
                'organization_id': str(org.id),
                'role': 'member'
            },
            context={'request': Request(request)}
        )

        assert serializer.is_valid(), serializer.errors
        invitation = serializer.save()

        assert invitation.email == 'invitee@example.com'
        assert invitation.organization == org
        assert invitation.invited_by == owner
        assert invitation.role == 'member'

    def test_email_normalization(self):
        """Test that email is normalized to lowercase"""
        owner = User.objects.create_user(
            email='owner@example.com',
            password='testpass123'
        )
        org = Organization.objects.create(
            name='Test Org',
            owner=owner
        )

        factory = APIRequestFactory()
        request = factory.post('/fake-url/')
        request.user = owner

        serializer = CreateInvitationSerializer(
            data={
                'email': 'Invitee@EXAMPLE.COM',
                'organization_id': str(org.id),
                'role': 'member'
            },
            context={'request': Request(request)}
        )

        assert serializer.is_valid()
        invitation = serializer.save()
        assert invitation.email == 'invitee@example.com'

    def test_prevent_duplicate_invitation(self):
        """Test that duplicate invitations are prevented"""
        owner = User.objects.create_user(
            email='owner@example.com',
            password='testpass123'
        )
        org = Organization.objects.create(
            name='Test Org',
            owner=owner
        )

        # Create existing invitation
        Invitation.objects.create(
            email='invitee@example.com',
            organization=org,
            invited_by=owner,
            role='member'
        )

        factory = APIRequestFactory()
        request = factory.post('/fake-url/')
        request.user = owner

        serializer = CreateInvitationSerializer(
            data={
                'email': 'invitee@example.com',
                'organization_id': str(org.id),
                'role': 'member'
            },
            context={'request': Request(request)}
        )

        assert not serializer.is_valid()
        assert 'email' in serializer.errors

    def test_prevent_inviting_existing_member(self):
        """Test that existing members can't be re-invited"""
        owner = User.objects.create_user(
            email='owner@example.com',
            password='testpass123'
        )
        member = User.objects.create_user(
            email='member@example.com',
            password='testpass123'
        )
        org = Organization.objects.create(
            name='Test Org',
            owner=owner
        )
        Membership.objects.create(
            user=member,
            organization=org,
            role='member'
        )

        factory = APIRequestFactory()
        request = factory.post('/fake-url/')
        request.user = owner

        serializer = CreateInvitationSerializer(
            data={
                'email': 'member@example.com',
                'organization_id': str(org.id),
                'role': 'admin'
            },
            context={'request': Request(request)}
        )

        assert not serializer.is_valid()
        assert 'email' in serializer.errors

    def test_expired_invitation_can_be_replaced(self):
        """Test that expired invitations can be replaced"""
        owner = User.objects.create_user(
            email='owner@example.com',
            password='testpass123'
        )
        org = Organization.objects.create(
            name='Test Org',
            owner=owner
        )

        # Create expired invitation
        expired_invitation = Invitation.objects.create(
            email='invitee@example.com',
            organization=org,
            invited_by=owner,
            role='member',
            expires_at=timezone.now() - timedelta(days=1)
        )

        factory = APIRequestFactory()
        request = factory.post('/fake-url/')
        request.user = owner

        serializer = CreateInvitationSerializer(
            data={
                'email': 'invitee@example.com',
                'organization_id': str(org.id),
                'role': 'member'
            },
            context={'request': Request(request)}
        )

        assert serializer.is_valid()
        serializer.save()

        # Old invitation should be deleted
        assert not Invitation.objects.filter(id=expired_invitation.id).exists()
        # New invitation should exist
        assert Invitation.objects.filter(email='invitee@example.com').count() == 1

    def test_invalid_organization_id(self):
        """Test that invalid organization ID is rejected"""
        owner = User.objects.create_user(
            email='owner@example.com',
            password='testpass123'
        )

        factory = APIRequestFactory()
        request = factory.post('/fake-url/')
        request.user = owner

        serializer = CreateInvitationSerializer(
            data={
                'email': 'invitee@example.com',
                'organization_id': '00000000-0000-0000-0000-000000000000',
                'role': 'member'
            },
            context={'request': Request(request)}
        )

        assert not serializer.is_valid()
        assert 'organization_id' in serializer.errors

    def test_required_fields(self):
        """Test that required fields are validated"""
        owner = User.objects.create_user(
            email='owner@example.com',
            password='testpass123'
        )

        factory = APIRequestFactory()
        request = factory.post('/fake-url/')
        request.user = owner

        # Missing email
        serializer = CreateInvitationSerializer(
            data={
                'organization_id': '00000000-0000-0000-0000-000000000000',
                'role': 'member'
            },
            context={'request': Request(request)}
        )
        assert not serializer.is_valid()
        assert 'email' in serializer.errors

        # Missing organization_id
        serializer = CreateInvitationSerializer(
            data={
                'email': 'invitee@example.com',
                'role': 'member'
            },
            context={'request': Request(request)}
        )
        assert not serializer.is_valid()
        assert 'organization_id' in serializer.errors
