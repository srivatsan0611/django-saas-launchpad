"""
Tests for Organization API views and endpoints.

Tests cover:
- Organization CRUD operations
- Membership management
- Invitation creation and acceptance
- RBAC enforcement for all endpoints
- Edge cases and error handling
"""

import pytest
from rest_framework.test import APIClient
from rest_framework import status
from django.utils import timezone
from datetime import timedelta
from unittest.mock import patch

from accounts.models import User
from organizations.models import Organization, Membership, Invitation


@pytest.fixture
def api_client():
    """Fixture for API client"""
    return APIClient()


@pytest.fixture
def owner_user(db):
    """Fixture for organization owner"""
    return User.objects.create_user(
        email='owner@example.com',
        password='testpass123'
    )


@pytest.fixture
def admin_user(db):
    """Fixture for organization admin"""
    return User.objects.create_user(
        email='admin@example.com',
        password='testpass123'
    )


@pytest.fixture
def member_user(db):
    """Fixture for organization member"""
    return User.objects.create_user(
        email='member@example.com',
        password='testpass123'
    )


@pytest.fixture
def outsider_user(db):
    """Fixture for non-member user"""
    return User.objects.create_user(
        email='outsider@example.com',
        password='testpass123'
    )


@pytest.fixture
def organization(owner_user):
    """Fixture for test organization"""
    org = Organization.objects.create(
        name='Test Organization',
        owner=owner_user
    )
    # Owner membership is auto-created by signal
    return org


@pytest.mark.django_db
class TestOrganizationViewSet:
    """Tests for OrganizationViewSet"""

    def test_list_organizations_authenticated(self, api_client, owner_user, organization):
        """Test listing organizations for authenticated user"""
        api_client.force_authenticate(user=owner_user)
        response = api_client.get('/api/organizations/')

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]['name'] == 'Test Organization'

    def test_list_organizations_unauthenticated(self, api_client):
        """Test that unauthenticated users can't list organizations"""
        response = api_client.get('/api/organizations/')

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_list_only_user_organizations(self, api_client, owner_user, outsider_user):
        """Test that users only see their own organizations"""
        # Create org for owner
        org1 = Organization.objects.create(
            name='Owner Org',
            owner=owner_user
        )

        # Create org for outsider
        org2 = Organization.objects.create(
            name='Outsider Org',
            owner=outsider_user
        )

        # Owner should only see their org
        api_client.force_authenticate(user=owner_user)
        response = api_client.get('/api/organizations/')

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]['name'] == 'Owner Org'

    def test_create_organization(self, api_client, owner_user):
        """Test creating an organization"""
        api_client.force_authenticate(user=owner_user)
        response = api_client.post('/api/organizations/', {
            'name': 'New Organization'
        })

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['name'] == 'New Organization'
        assert response.data['slug'] == 'new-organization'

        # Verify organization was created in database
        org = Organization.objects.get(name='New Organization')
        assert org.owner == owner_user

        # Verify owner membership was created (by signal and viewset)
        assert Membership.objects.filter(
            user=owner_user,
            organization=org,
            role='owner'
        ).exists()

    def test_retrieve_organization_as_member(self, api_client, member_user, organization):
        """Test retrieving organization details as member"""
        Membership.objects.create(
            user=member_user,
            organization=organization,
            role='member'
        )

        api_client.force_authenticate(user=member_user)
        response = api_client.get(f'/api/organizations/{organization.id}/')

        assert response.status_code == status.HTTP_200_OK
        assert response.data['name'] == 'Test Organization'

    def test_retrieve_organization_as_non_member(self, api_client, outsider_user, organization):
        """Test that non-members can't retrieve organization"""
        api_client.force_authenticate(user=outsider_user)
        response = api_client.get(f'/api/organizations/{organization.id}/')

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_update_organization_as_owner(self, api_client, owner_user, organization):
        """Test updating organization as owner"""
        api_client.force_authenticate(user=owner_user)
        response = api_client.patch(f'/api/organizations/{organization.id}/', {
            'name': 'Updated Organization'
        })

        assert response.status_code == status.HTTP_200_OK
        assert response.data['name'] == 'Updated Organization'

        organization.refresh_from_db()
        assert organization.name == 'Updated Organization'

    def test_update_organization_as_admin(self, api_client, admin_user, organization):
        """Test that admin can't update organization"""
        Membership.objects.create(
            user=admin_user,
            organization=organization,
            role='admin'
        )

        api_client.force_authenticate(user=admin_user)
        response = api_client.patch(f'/api/organizations/{organization.id}/', {
            'name': 'Updated Organization'
        })

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_delete_organization_as_owner(self, api_client, owner_user, organization):
        """Test deleting organization as owner"""
        org_id = organization.id
        api_client.force_authenticate(user=owner_user)
        response = api_client.delete(f'/api/organizations/{organization.id}/')

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Organization.objects.filter(id=org_id).exists()

    def test_delete_organization_as_non_owner(self, api_client, member_user, organization):
        """Test that non-owner can't delete organization"""
        Membership.objects.create(
            user=member_user,
            organization=organization,
            role='member'
        )

        api_client.force_authenticate(user=member_user)
        response = api_client.delete(f'/api/organizations/{organization.id}/')

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert Organization.objects.filter(id=organization.id).exists()


@pytest.mark.django_db
class TestMembershipViewSet:
    """Tests for MembershipViewSet"""

    def test_list_members(self, api_client, owner_user, member_user, organization):
        """Test listing organization members"""
        Membership.objects.create(
            user=member_user,
            organization=organization,
            role='member'
        )

        api_client.force_authenticate(user=owner_user)
        response = api_client.get(f'/api/organizations/{organization.id}/members/')

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 2  # owner + member

    def test_list_members_as_non_member(self, api_client, outsider_user, organization):
        """Test that non-members can't list members"""
        api_client.force_authenticate(user=outsider_user)
        response = api_client.get(f'/api/organizations/{organization.id}/members/')

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_remove_member_as_admin(self, api_client, admin_user, member_user, organization):
        """Test removing a member as admin"""
        Membership.objects.create(
            user=admin_user,
            organization=organization,
            role='admin'
        )
        membership = Membership.objects.create(
            user=member_user,
            organization=organization,
            role='member'
        )

        api_client.force_authenticate(user=admin_user)
        response = api_client.delete(
            f'/api/organizations/{organization.id}/members/{membership.id}/'
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Membership.objects.filter(id=membership.id).exists()

    def test_cannot_remove_owner(self, api_client, owner_user, organization):
        """Test that owner cannot be removed"""
        owner_membership = Membership.objects.get(
            user=owner_user,
            organization=organization
        )

        api_client.force_authenticate(user=owner_user)
        response = api_client.delete(
            f'/api/organizations/{organization.id}/members/{owner_membership.id}/'
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert Membership.objects.filter(id=owner_membership.id).exists()

    def test_cannot_remove_self(self, api_client, member_user, organization):
        """Test that users cannot remove themselves"""
        membership = Membership.objects.create(
            user=member_user,
            organization=organization,
            role='member'
        )

        api_client.force_authenticate(user=member_user)
        response = api_client.delete(
            f'/api/organizations/{organization.id}/members/{membership.id}/'
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert Membership.objects.filter(id=membership.id).exists()

    def test_change_role_as_owner(self, api_client, owner_user, member_user, organization):
        """Test changing member role as owner"""
        membership = Membership.objects.create(
            user=member_user,
            organization=organization,
            role='member'
        )

        api_client.force_authenticate(user=owner_user)
        response = api_client.post(
            f'/api/organizations/{organization.id}/members/{membership.id}/change-role/',
            {'role': 'admin'}
        )

        assert response.status_code == status.HTTP_200_OK
        membership.refresh_from_db()
        assert membership.role == 'admin'

    def test_cannot_change_owner_role(self, api_client, owner_user, organization):
        """Test that owner's role cannot be changed"""
        owner_membership = Membership.objects.get(
            user=owner_user,
            organization=organization
        )

        api_client.force_authenticate(user=owner_user)
        response = api_client.post(
            f'/api/organizations/{organization.id}/members/{owner_membership.id}/change-role/',
            {'role': 'admin'}
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        owner_membership.refresh_from_db()
        assert owner_membership.role == 'owner'

    def test_change_role_as_non_owner(self, api_client, admin_user, member_user, organization):
        """Test that non-owner can't change roles"""
        Membership.objects.create(
            user=admin_user,
            organization=organization,
            role='admin'
        )
        membership = Membership.objects.create(
            user=member_user,
            organization=organization,
            role='member'
        )

        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            f'/api/organizations/{organization.id}/members/{membership.id}/change-role/',
            {'role': 'admin'}
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestInvitationViewSet:
    """Tests for InvitationViewSet"""

    @patch('organizations.tasks.send_invitation_email.delay')
    def test_create_invitation(self, mock_send_email, api_client, owner_user, organization):
        """Test creating an invitation"""
        api_client.force_authenticate(user=owner_user)
        response = api_client.post(
            f'/api/organizations/{organization.id}/invitations/',
            {
                'email': 'invitee@example.com',
                'role': 'member'
            }
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['email'] == 'invitee@example.com'
        assert response.data['role'] == 'member'

        # Verify invitation was created
        invitation = Invitation.objects.get(email='invitee@example.com')
        assert invitation.organization == organization
        assert invitation.invited_by == owner_user

        # Verify email task was called
        mock_send_email.assert_called_once()

    def test_create_invitation_as_member(self, api_client, member_user, organization):
        """Test that regular member can't create invitations"""
        Membership.objects.create(
            user=member_user,
            organization=organization,
            role='member'
        )

        api_client.force_authenticate(user=member_user)
        response = api_client.post(
            f'/api/organizations/{organization.id}/invitations/',
            {
                'email': 'invitee@example.com',
                'role': 'member'
            }
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_list_invitations(self, api_client, owner_user, organization):
        """Test listing organization invitations"""
        Invitation.objects.create(
            email='invitee1@example.com',
            organization=organization,
            invited_by=owner_user,
            role='member'
        )
        Invitation.objects.create(
            email='invitee2@example.com',
            organization=organization,
            invited_by=owner_user,
            role='admin'
        )

        api_client.force_authenticate(user=owner_user)
        response = api_client.get(f'/api/organizations/{organization.id}/invitations/')

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 2

    def test_accept_invitation(self, api_client, owner_user, outsider_user, organization):
        """Test accepting an invitation"""
        invitation = Invitation.objects.create(
            email='outsider@example.com',
            organization=organization,
            invited_by=owner_user,
            role='member'
        )

        api_client.force_authenticate(user=outsider_user)
        response = api_client.post(
            f'/api/organizations/{organization.id}/invitations/accept/',
            {'token': str(invitation.token)}
        )

        assert response.status_code == status.HTTP_200_OK
        assert 'organization' in response.data
        assert 'membership' in response.data

        # Verify membership was created
        assert Membership.objects.filter(
            user=outsider_user,
            organization=organization,
            role='member'
        ).exists()

        # Verify invitation was marked as accepted
        invitation.refresh_from_db()
        assert invitation.is_accepted()

    def test_accept_expired_invitation(self, api_client, owner_user, outsider_user, organization):
        """Test that expired invitations can't be accepted"""
        invitation = Invitation.objects.create(
            email='outsider@example.com',
            organization=organization,
            invited_by=owner_user,
            role='member',
            expires_at=timezone.now() - timedelta(days=1)
        )

        api_client.force_authenticate(user=outsider_user)
        response = api_client.post(
            f'/api/organizations/{organization.id}/invitations/accept/',
            {'token': str(invitation.token)}
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_accept_invitation_wrong_email(self, api_client, owner_user, member_user, organization):
        """Test that wrong user can't accept invitation"""
        invitation = Invitation.objects.create(
            email='outsider@example.com',
            organization=organization,
            invited_by=owner_user,
            role='member'
        )

        # Member user tries to accept invitation meant for outsider
        api_client.force_authenticate(user=member_user)
        response = api_client.post(
            f'/api/organizations/{organization.id}/invitations/accept/',
            {'token': str(invitation.token)}
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_my_invitations(self, api_client, owner_user, outsider_user):
        """Test listing current user's pending invitations"""
        org1 = Organization.objects.create(name='Org 1', owner=owner_user)
        org2 = Organization.objects.create(name='Org 2', owner=owner_user)

        # Create invitations for outsider
        Invitation.objects.create(
            email='outsider@example.com',
            organization=org1,
            invited_by=owner_user,
            role='member'
        )
        Invitation.objects.create(
            email='outsider@example.com',
            organization=org2,
            invited_by=owner_user,
            role='admin'
        )

        api_client.force_authenticate(user=outsider_user)
        response = api_client.get('/api/invitations/my-invitations/')

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 2

    def test_delete_invitation(self, api_client, owner_user, organization):
        """Test deleting an invitation"""
        invitation = Invitation.objects.create(
            email='invitee@example.com',
            organization=organization,
            invited_by=owner_user,
            role='member'
        )

        api_client.force_authenticate(user=owner_user)
        response = api_client.delete(
            f'/api/organizations/{organization.id}/invitations/{invitation.id}/'
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Invitation.objects.filter(id=invitation.id).exists()
