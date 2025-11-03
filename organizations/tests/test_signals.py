"""
Tests for Organization signal handlers.

Tests cover:
- Automatic owner membership creation on organization creation
- Signal behavior on organization updates
"""

import pytest
from accounts.models import User
from organizations.models import Organization, Membership


@pytest.mark.django_db
class TestOrganizationSignals:
    """Tests for Organization signal handlers"""

    def test_owner_membership_created_on_organization_creation(self):
        """Test that owner membership is automatically created"""
        user = User.objects.create_user(
            email='owner@example.com',
            password='testpass123'
        )

        # Verify no memberships exist yet
        assert Membership.objects.count() == 0

        # Create organization
        org = Organization.objects.create(
            name='Test Org',
            owner=user
        )

        # Verify owner membership was created
        assert Membership.objects.count() == 1

        membership = Membership.objects.get(user=user, organization=org)
        assert membership.role == 'owner'
        assert membership.user == user
        assert membership.organization == org

    def test_no_duplicate_membership_on_update(self):
        """Test that updating organization doesn't create duplicate membership"""
        user = User.objects.create_user(
            email='owner@example.com',
            password='testpass123'
        )

        org = Organization.objects.create(
            name='Test Org',
            owner=user
        )

        # Verify one membership exists
        assert Membership.objects.filter(user=user, organization=org).count() == 1

        # Update organization
        org.name = 'Updated Org Name'
        org.save()

        # Verify still only one membership
        assert Membership.objects.filter(user=user, organization=org).count() == 1

    def test_multiple_organizations_same_owner(self):
        """Test that one user can be owner of multiple organizations"""
        user = User.objects.create_user(
            email='owner@example.com',
            password='testpass123'
        )

        # Create first organization
        org1 = Organization.objects.create(
            name='Test Org 1',
            owner=user
        )

        # Create second organization
        org2 = Organization.objects.create(
            name='Test Org 2',
            owner=user
        )

        # Verify both owner memberships exist
        assert Membership.objects.filter(user=user, role='owner').count() == 2
        assert Membership.objects.filter(user=user, organization=org1).exists()
        assert Membership.objects.filter(user=user, organization=org2).exists()

    def test_different_owners_different_organizations(self):
        """Test that different organizations can have different owners"""
        owner1 = User.objects.create_user(
            email='owner1@example.com',
            password='testpass123'
        )
        owner2 = User.objects.create_user(
            email='owner2@example.com',
            password='testpass123'
        )

        org1 = Organization.objects.create(
            name='Test Org 1',
            owner=owner1
        )
        org2 = Organization.objects.create(
            name='Test Org 2',
            owner=owner2
        )

        # Verify each owner has their own membership
        assert Membership.objects.filter(user=owner1, organization=org1, role='owner').exists()
        assert Membership.objects.filter(user=owner2, organization=org2, role='owner').exists()

        # Verify cross-memberships don't exist
        assert not Membership.objects.filter(user=owner1, organization=org2).exists()
        assert not Membership.objects.filter(user=owner2, organization=org1).exists()
