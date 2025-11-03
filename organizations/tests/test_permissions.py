"""
Tests for Organization RBAC permissions.

Tests cover:
- IsOrganizationOwner permission
- IsOrganizationAdminOrOwner permission
- IsOrganizationMember permission
"""

import pytest
from rest_framework.test import APIRequestFactory
from django.contrib.auth.models import AnonymousUser

from accounts.models import User
from organizations.models import Organization, Membership
from organizations.permissions import (
    IsOrganizationOwner,
    IsOrganizationAdminOrOwner,
    IsOrganizationMember
)


class MockView:
    """Mock view for permission testing"""
    def __init__(self, organization):
        self.kwargs = {'organization_pk': str(organization.id)}


@pytest.mark.django_db
class TestIsOrganizationOwner:
    """Tests for IsOrganizationOwner permission"""

    def test_owner_has_permission(self):
        """Test that organization owner has permission"""
        owner = User.objects.create_user(
            email='owner@example.com',
            password='testpass123'
        )
        org = Organization.objects.create(
            name='Test Org',
            owner=owner
        )
        Membership.objects.create(user=owner, organization=org, role='owner')

        factory = APIRequestFactory()
        request = factory.get('/fake-url/')
        request.user = owner

        permission = IsOrganizationOwner()
        view = MockView(org)

        assert permission.has_permission(request, view)

    def test_admin_no_permission(self):
        """Test that admin does not have owner permission"""
        owner = User.objects.create_user(
            email='owner@example.com',
            password='testpass123'
        )
        admin = User.objects.create_user(
            email='admin@example.com',
            password='testpass123'
        )
        org = Organization.objects.create(
            name='Test Org',
            owner=owner
        )
        Membership.objects.create(user=owner, organization=org, role='owner')
        Membership.objects.create(user=admin, organization=org, role='admin')

        factory = APIRequestFactory()
        request = factory.get('/fake-url/')
        request.user = admin

        permission = IsOrganizationOwner()
        view = MockView(org)

        assert not permission.has_permission(request, view)

    def test_member_no_permission(self):
        """Test that member does not have owner permission"""
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
        Membership.objects.create(user=owner, organization=org, role='owner')
        Membership.objects.create(user=member, organization=org, role='member')

        factory = APIRequestFactory()
        request = factory.get('/fake-url/')
        request.user = member

        permission = IsOrganizationOwner()
        view = MockView(org)

        assert not permission.has_permission(request, view)

    def test_non_member_no_permission(self):
        """Test that non-member does not have permission"""
        owner = User.objects.create_user(
            email='owner@example.com',
            password='testpass123'
        )
        outsider = User.objects.create_user(
            email='outsider@example.com',
            password='testpass123'
        )
        org = Organization.objects.create(
            name='Test Org',
            owner=owner
        )
        Membership.objects.create(user=owner, organization=org, role='owner')

        factory = APIRequestFactory()
        request = factory.get('/fake-url/')
        request.user = outsider

        permission = IsOrganizationOwner()
        view = MockView(org)

        assert not permission.has_permission(request, view)

    def test_anonymous_user_no_permission(self):
        """Test that anonymous user does not have permission"""
        owner = User.objects.create_user(
            email='owner@example.com',
            password='testpass123'
        )
        org = Organization.objects.create(
            name='Test Org',
            owner=owner
        )
        Membership.objects.create(user=owner, organization=org, role='owner')

        factory = APIRequestFactory()
        request = factory.get('/fake-url/')
        request.user = AnonymousUser()

        permission = IsOrganizationOwner()
        view = MockView(org)

        assert not permission.has_permission(request, view)


@pytest.mark.django_db
class TestIsOrganizationAdminOrOwner:
    """Tests for IsOrganizationAdminOrOwner permission"""

    def test_owner_has_permission(self):
        """Test that owner has permission"""
        owner = User.objects.create_user(
            email='owner@example.com',
            password='testpass123'
        )
        org = Organization.objects.create(
            name='Test Org',
            owner=owner
        )
        Membership.objects.create(user=owner, organization=org, role='owner')

        factory = APIRequestFactory()
        request = factory.get('/fake-url/')
        request.user = owner

        permission = IsOrganizationAdminOrOwner()
        view = MockView(org)

        assert permission.has_permission(request, view)

    def test_admin_has_permission(self):
        """Test that admin has permission"""
        owner = User.objects.create_user(
            email='owner@example.com',
            password='testpass123'
        )
        admin = User.objects.create_user(
            email='admin@example.com',
            password='testpass123'
        )
        org = Organization.objects.create(
            name='Test Org',
            owner=owner
        )
        Membership.objects.create(user=owner, organization=org, role='owner')
        Membership.objects.create(user=admin, organization=org, role='admin')

        factory = APIRequestFactory()
        request = factory.get('/fake-url/')
        request.user = admin

        permission = IsOrganizationAdminOrOwner()
        view = MockView(org)

        assert permission.has_permission(request, view)

    def test_member_no_permission(self):
        """Test that regular member does not have permission"""
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
        Membership.objects.create(user=owner, organization=org, role='owner')
        Membership.objects.create(user=member, organization=org, role='member')

        factory = APIRequestFactory()
        request = factory.get('/fake-url/')
        request.user = member

        permission = IsOrganizationAdminOrOwner()
        view = MockView(org)

        assert not permission.has_permission(request, view)

    def test_non_member_no_permission(self):
        """Test that non-member does not have permission"""
        owner = User.objects.create_user(
            email='owner@example.com',
            password='testpass123'
        )
        outsider = User.objects.create_user(
            email='outsider@example.com',
            password='testpass123'
        )
        org = Organization.objects.create(
            name='Test Org',
            owner=owner
        )
        Membership.objects.create(user=owner, organization=org, role='owner')

        factory = APIRequestFactory()
        request = factory.get('/fake-url/')
        request.user = outsider

        permission = IsOrganizationAdminOrOwner()
        view = MockView(org)

        assert not permission.has_permission(request, view)


@pytest.mark.django_db
class TestIsOrganizationMember:
    """Tests for IsOrganizationMember permission"""

    def test_owner_has_permission(self):
        """Test that owner has permission"""
        owner = User.objects.create_user(
            email='owner@example.com',
            password='testpass123'
        )
        org = Organization.objects.create(
            name='Test Org',
            owner=owner
        )
        Membership.objects.create(user=owner, organization=org, role='owner')

        factory = APIRequestFactory()
        request = factory.get('/fake-url/')
        request.user = owner

        permission = IsOrganizationMember()
        view = MockView(org)

        assert permission.has_permission(request, view)

    def test_admin_has_permission(self):
        """Test that admin has permission"""
        owner = User.objects.create_user(
            email='owner@example.com',
            password='testpass123'
        )
        admin = User.objects.create_user(
            email='admin@example.com',
            password='testpass123'
        )
        org = Organization.objects.create(
            name='Test Org',
            owner=owner
        )
        Membership.objects.create(user=owner, organization=org, role='owner')
        Membership.objects.create(user=admin, organization=org, role='admin')

        factory = APIRequestFactory()
        request = factory.get('/fake-url/')
        request.user = admin

        permission = IsOrganizationMember()
        view = MockView(org)

        assert permission.has_permission(request, view)

    def test_member_has_permission(self):
        """Test that regular member has permission"""
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
        Membership.objects.create(user=owner, organization=org, role='owner')
        Membership.objects.create(user=member, organization=org, role='member')

        factory = APIRequestFactory()
        request = factory.get('/fake-url/')
        request.user = member

        permission = IsOrganizationMember()
        view = MockView(org)

        assert permission.has_permission(request, view)

    def test_non_member_no_permission(self):
        """Test that non-member does not have permission"""
        owner = User.objects.create_user(
            email='owner@example.com',
            password='testpass123'
        )
        outsider = User.objects.create_user(
            email='outsider@example.com',
            password='testpass123'
        )
        org = Organization.objects.create(
            name='Test Org',
            owner=owner
        )
        Membership.objects.create(user=owner, organization=org, role='owner')

        factory = APIRequestFactory()
        request = factory.get('/fake-url/')
        request.user = outsider

        permission = IsOrganizationMember()
        view = MockView(org)

        assert not permission.has_permission(request, view)

    def test_anonymous_user_no_permission(self):
        """Test that anonymous user does not have permission"""
        owner = User.objects.create_user(
            email='owner@example.com',
            password='testpass123'
        )
        org = Organization.objects.create(
            name='Test Org',
            owner=owner
        )
        Membership.objects.create(user=owner, organization=org, role='owner')

        factory = APIRequestFactory()
        request = factory.get('/fake-url/')
        request.user = AnonymousUser()

        permission = IsOrganizationMember()
        view = MockView(org)

        assert not permission.has_permission(request, view)
