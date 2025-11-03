"""
Tests for Organization, Membership, and Invitation models.

Tests cover:
- Model creation and field validation
- Auto-generated fields (slug, tokens, expiry dates)
- Model methods and properties
- Uniqueness constraints
- Related object behavior
"""

import pytest
from django.utils import timezone
from datetime import timedelta
from django.db.utils import IntegrityError
from accounts.models import User
from organizations.models import Organization, Membership, Invitation


@pytest.mark.django_db
class TestOrganizationModel:
    """Tests for Organization model"""

    def test_create_organization(self):
        """Test basic organization creation"""
        user = User.objects.create_user(
            email='owner@example.com',
            password='testpass123'
        )
        org = Organization.objects.create(
            name='Test Org',
            owner=user
        )

        assert org.id is not None
        assert org.name == 'Test Org'
        assert org.owner == user
        assert org.slug == 'test-org'
        assert org.created_at is not None
        assert org.updated_at is not None

    def test_slug_auto_generation(self):
        """Test that slug is automatically generated from name"""
        user = User.objects.create_user(
            email='owner@example.com',
            password='testpass123'
        )
        org = Organization.objects.create(
            name='My Amazing Organization',
            owner=user
        )

        assert org.slug == 'my-amazing-organization'

    def test_slug_uniqueness_with_counter(self):
        """Test that duplicate slugs get a counter appended"""
        user = User.objects.create_user(
            email='owner@example.com',
            password='testpass123'
        )

        org1 = Organization.objects.create(
            name='Test Org',
            owner=user
        )
        org2 = Organization.objects.create(
            name='Test Org',
            owner=user
        )
        org3 = Organization.objects.create(
            name='Test Org',
            owner=user
        )

        assert org1.slug == 'test-org'
        assert org2.slug == 'test-org-1'
        assert org3.slug == 'test-org-2'

    def test_slug_unique_constraint(self):
        """Test that slug must be unique"""
        user = User.objects.create_user(
            email='owner@example.com',
            password='testpass123'
        )

        Organization.objects.create(
            name='Test Org',
            slug='custom-slug',
            owner=user
        )

        with pytest.raises(IntegrityError):
            Organization.objects.create(
                name='Another Org',
                slug='custom-slug',
                owner=user
            )

    def test_get_member_count(self):
        """Test member count calculation"""
        user = User.objects.create_user(
            email='owner@example.com',
            password='testpass123'
        )
        org = Organization.objects.create(
            name='Test Org',
            owner=user
        )

        # Initially no memberships
        assert org.get_member_count() == 0

        # Create memberships
        Membership.objects.create(user=user, organization=org, role='owner')
        assert org.get_member_count() == 1

        user2 = User.objects.create_user(
            email='member@example.com',
            password='testpass123'
        )
        Membership.objects.create(user=user2, organization=org, role='member')
        assert org.get_member_count() == 2

    def test_organization_str(self):
        """Test string representation"""
        user = User.objects.create_user(
            email='owner@example.com',
            password='testpass123'
        )
        org = Organization.objects.create(
            name='Test Organization',
            owner=user
        )

        assert str(org) == 'Test Organization'


@pytest.mark.django_db
class TestMembershipModel:
    """Tests for Membership model"""

    def test_create_membership(self):
        """Test basic membership creation"""
        user = User.objects.create_user(
            email='user@example.com',
            password='testpass123'
        )
        owner = User.objects.create_user(
            email='owner@example.com',
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

        assert membership.user == user
        assert membership.organization == org
        assert membership.role == 'member'
        assert membership.joined_at is not None

    def test_membership_unique_together(self):
        """Test that user can't have duplicate membership in same org"""
        user = User.objects.create_user(
            email='user@example.com',
            password='testpass123'
        )
        owner = User.objects.create_user(
            email='owner@example.com',
            password='testpass123'
        )
        org = Organization.objects.create(
            name='Test Org',
            owner=owner
        )

        Membership.objects.create(
            user=user,
            organization=org,
            role='member'
        )

        with pytest.raises(IntegrityError):
            Membership.objects.create(
                user=user,
                organization=org,
                role='admin'
            )

    def test_membership_roles(self):
        """Test different membership roles"""
        user = User.objects.create_user(
            email='user@example.com',
            password='testpass123'
        )
        owner = User.objects.create_user(
            email='owner@example.com',
            password='testpass123'
        )
        org = Organization.objects.create(
            name='Test Org',
            owner=owner
        )

        # Test owner role
        owner_membership = Membership.objects.create(
            user=owner,
            organization=org,
            role='owner'
        )
        assert owner_membership.is_owner()
        assert owner_membership.is_admin_or_owner()

        # Test admin role
        admin = User.objects.create_user(
            email='admin@example.com',
            password='testpass123'
        )
        admin_membership = Membership.objects.create(
            user=admin,
            organization=org,
            role='admin'
        )
        assert not admin_membership.is_owner()
        assert admin_membership.is_admin_or_owner()

        # Test member role
        member_membership = Membership.objects.create(
            user=user,
            organization=org,
            role='member'
        )
        assert not member_membership.is_owner()
        assert not member_membership.is_admin_or_owner()

    def test_membership_str(self):
        """Test string representation"""
        user = User.objects.create_user(
            email='user@example.com',
            password='testpass123'
        )
        owner = User.objects.create_user(
            email='owner@example.com',
            password='testpass123'
        )
        org = Organization.objects.create(
            name='Test Org',
            owner=owner
        )
        membership = Membership.objects.create(
            user=user,
            organization=org,
            role='admin'
        )

        assert str(membership) == 'user@example.com - Test Org (admin)'


@pytest.mark.django_db
class TestInvitationModel:
    """Tests for Invitation model"""

    def test_create_invitation(self):
        """Test basic invitation creation"""
        user = User.objects.create_user(
            email='inviter@example.com',
            password='testpass123'
        )
        org = Organization.objects.create(
            name='Test Org',
            owner=user
        )

        invitation = Invitation.objects.create(
            email='invitee@example.com',
            organization=org,
            invited_by=user,
            role='member'
        )

        assert invitation.email == 'invitee@example.com'
        assert invitation.organization == org
        assert invitation.invited_by == user
        assert invitation.role == 'member'
        assert invitation.token is not None
        assert invitation.expires_at is not None
        assert invitation.accepted_at is None
        assert invitation.created_at is not None

    def test_invitation_auto_expiry(self):
        """Test that expiry is automatically set to 7 days"""
        user = User.objects.create_user(
            email='inviter@example.com',
            password='testpass123'
        )
        org = Organization.objects.create(
            name='Test Org',
            owner=user
        )

        now = timezone.now()
        invitation = Invitation.objects.create(
            email='invitee@example.com',
            organization=org,
            invited_by=user,
            role='member'
        )

        # Check expiry is approximately 7 days from now
        expected_expiry = now + timedelta(days=7)
        time_diff = abs((invitation.expires_at - expected_expiry).total_seconds())
        assert time_diff < 2  # Within 2 seconds

    def test_invitation_unique_together(self):
        """Test that email+org combination is unique"""
        user = User.objects.create_user(
            email='inviter@example.com',
            password='testpass123'
        )
        org = Organization.objects.create(
            name='Test Org',
            owner=user
        )

        Invitation.objects.create(
            email='invitee@example.com',
            organization=org,
            invited_by=user,
            role='member'
        )

        with pytest.raises(IntegrityError):
            Invitation.objects.create(
                email='invitee@example.com',
                organization=org,
                invited_by=user,
                role='admin'
            )

    def test_is_expired(self):
        """Test invitation expiry check"""
        user = User.objects.create_user(
            email='inviter@example.com',
            password='testpass123'
        )
        org = Organization.objects.create(
            name='Test Org',
            owner=user
        )

        # Create non-expired invitation
        invitation = Invitation.objects.create(
            email='invitee@example.com',
            organization=org,
            invited_by=user,
            role='member'
        )
        assert not invitation.is_expired()

        # Create expired invitation
        expired_invitation = Invitation.objects.create(
            email='expired@example.com',
            organization=org,
            invited_by=user,
            role='member',
            expires_at=timezone.now() - timedelta(days=1)
        )
        assert expired_invitation.is_expired()

    def test_is_accepted(self):
        """Test invitation acceptance check"""
        user = User.objects.create_user(
            email='inviter@example.com',
            password='testpass123'
        )
        org = Organization.objects.create(
            name='Test Org',
            owner=user
        )

        # Create pending invitation
        invitation = Invitation.objects.create(
            email='invitee@example.com',
            organization=org,
            invited_by=user,
            role='member'
        )
        assert not invitation.is_accepted()

        # Accept invitation
        invitation.accepted_at = timezone.now()
        invitation.save()
        assert invitation.is_accepted()

    def test_can_accept(self):
        """Test if invitation can be accepted"""
        user = User.objects.create_user(
            email='inviter@example.com',
            password='testpass123'
        )
        org = Organization.objects.create(
            name='Test Org',
            owner=user
        )

        # Valid invitation
        valid_invitation = Invitation.objects.create(
            email='valid@example.com',
            organization=org,
            invited_by=user,
            role='member'
        )
        assert valid_invitation.can_accept()

        # Expired invitation
        expired_invitation = Invitation.objects.create(
            email='expired@example.com',
            organization=org,
            invited_by=user,
            role='member',
            expires_at=timezone.now() - timedelta(days=1)
        )
        assert not expired_invitation.can_accept()

        # Accepted invitation
        accepted_invitation = Invitation.objects.create(
            email='accepted@example.com',
            organization=org,
            invited_by=user,
            role='member',
            accepted_at=timezone.now()
        )
        assert not accepted_invitation.can_accept()

    def test_invitation_str(self):
        """Test string representation"""
        user = User.objects.create_user(
            email='inviter@example.com',
            password='testpass123'
        )
        org = Organization.objects.create(
            name='Test Org',
            owner=user
        )
        invitation = Invitation.objects.create(
            email='invitee@example.com',
            organization=org,
            invited_by=user,
            role='member'
        )

        assert str(invitation) == 'Invitation for invitee@example.com to Test Org'
