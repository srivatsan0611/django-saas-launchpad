from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.utils import timezone

from .models import Organization, Membership, Invitation
from .serializers import (
    OrganizationSerializer,
    CreateOrganizationSerializer,
    MembershipSerializer,
    UpdateMembershipSerializer,
    InvitationSerializer,
    CreateInvitationSerializer
)
from .permissions import (
    IsOrganizationOwner,
    IsOrganizationAdminOrOwner,
    IsOrganizationMember
)


class OrganizationViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing organizations.

    list: Returns organizations where the current user is a member
    create: Creates a new organization with current user as owner
    retrieve: Gets a specific organization (must be a member)
    update: Updates an organization (only owner can update)
    destroy: Deletes an organization (only owner can delete)
    """

    def get_permissions(self):
        """
        Apply different permissions based on the action.
        - list, create: Authenticated users only
        - retrieve: Organization members only
        - update, partial_update, destroy: Organization owners only
        """
        if self.action in ['update', 'partial_update', 'destroy']:
            return [IsAuthenticated(), IsOrganizationOwner()]
        elif self.action == 'retrieve':
            return [IsAuthenticated(), IsOrganizationMember()]
        return [IsAuthenticated()]

    def get_queryset(self):
        """Return only organizations where the user is a member"""
        user = self.request.user
        return Organization.objects.filter(
            memberships__user=user
        ).distinct().order_by('-created_at')

    def get_serializer_class(self):
        """Use different serializers for create vs read operations"""
        if self.action == 'create':
            return CreateOrganizationSerializer
        return OrganizationSerializer

    def perform_create(self, serializer):
        """
        Create organization. Owner membership is auto-created by signal.
        """
        serializer.save()


class MembershipViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing organization memberships.

    list: Lists all members of an organization
    destroy: Removes a member from the organization (admin/owner only)
    change_role: Changes a member's role (owner only)
    """
    serializer_class = MembershipSerializer

    def get_permissions(self):
        """
        Apply different permissions based on the action.
        - list: Organization members can view members
        - destroy: Only admins and owners can remove members
        - change_role: Only owners can change roles
        """
        if self.action == 'list':
            return [IsAuthenticated(), IsOrganizationMember()]
        elif self.action == 'destroy':
            return [IsAuthenticated(), IsOrganizationAdminOrOwner()]
        elif self.action == 'change_role':
            return [IsAuthenticated(), IsOrganizationOwner()]
        return [IsAuthenticated()]

    def get_queryset(self):
        """Return memberships for the specified organization"""
        organization_id = self.kwargs.get('organization_pk')
        if organization_id:
            return Membership.objects.filter(
                organization_id=organization_id
            ).select_related('user', 'organization').order_by('-joined_at')
        return Membership.objects.none()

    def destroy(self, request, *args, **kwargs):
        """
        Remove a member from the organization.
        Permissions are checked by IsOrganizationAdminOrOwner.
        Additional business logic: owner cannot be removed.
        """
        membership = self.get_object()

        # Cannot remove the owner
        if membership.is_owner():
            return Response(
                {'detail': 'Cannot remove the organization owner.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Cannot remove yourself
        if membership.user == request.user:
            return Response(
                {'detail': 'You cannot remove yourself. Leave the organization instead.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=['post'])
    def change_role(self, request, organization_pk=None, pk=None):
        """
        Change a member's role.
        Permissions are checked by IsOrganizationOwner.
        Additional business logic: cannot change owner's role.
        """
        membership = self.get_object()

        # Cannot change owner's role
        if membership.is_owner():
            return Response(
                {'detail': 'Cannot change the owner\'s role.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate and update role
        serializer = UpdateMembershipSerializer(
            membership,
            data=request.data,
            partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            MembershipSerializer(membership).data,
            status=status.HTTP_200_OK
        )


class InvitationViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing organization invitations.

    list: Lists invitations for an organization (admin/owner only)
    create: Creates a new invitation (admin/owner only)
    destroy: Cancels an invitation (admin/owner only)
    accept: Accepts an invitation (the invited user)
    my_invitations: Lists current user's pending invitations
    """

    def get_permissions(self):
        """
        Apply different permissions based on the action.
        - list, create, destroy: Only admins and owners
        - accept_invitation, my_invitations: Any authenticated user
        """
        if self.action in ['list', 'create', 'destroy']:
            return [IsAuthenticated(), IsOrganizationAdminOrOwner()]
        return [IsAuthenticated()]

    def get_queryset(self):
        """Return invitations for the specified organization"""
        organization_id = self.kwargs.get('organization_pk')
        if organization_id:
            return Invitation.objects.filter(
                organization_id=organization_id
            ).select_related('organization', 'invited_by').order_by('-created_at')
        return Invitation.objects.none()

    def get_serializer_class(self):
        """Use different serializers for create vs read operations"""
        if self.action == 'create':
            return CreateInvitationSerializer
        return InvitationSerializer

    def create(self, request, *args, **kwargs):
        """
        Create invitation.
        Permissions are checked by IsOrganizationAdminOrOwner.
        """
        organization_id = self.kwargs.get('organization_pk')

        # Add organization_id to request data
        data = request.data.copy()
        data['organization_id'] = organization_id

        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        invitation = serializer.save()

        # TODO: Send invitation email (will be implemented in Phase 2.6)

        return Response(
            InvitationSerializer(invitation).data,
            status=status.HTTP_201_CREATED
        )

    @action(detail=False, methods=['post'], url_path='accept')
    def accept_invitation(self, request, *args, **kwargs):
        """
        Accept an invitation using a token.
        Any authenticated user can accept if they have the token.
        """
        token = request.data.get('token')
        if not token:
            return Response(
                {'detail': 'Token is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            invitation = Invitation.objects.get(token=token)
        except Invitation.DoesNotExist:
            return Response(
                {'detail': 'Invalid invitation token.'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Check if invitation can be accepted
        if not invitation.can_accept():
            if invitation.is_expired():
                return Response(
                    {'detail': 'This invitation has expired.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if invitation.is_accepted():
                return Response(
                    {'detail': 'This invitation has already been accepted.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        # Check if invited email matches current user
        if invitation.email.lower() != request.user.email.lower():
            return Response(
                {'detail': 'This invitation was sent to a different email address.'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Check if user is already a member
        if Membership.objects.filter(
            user=request.user,
            organization=invitation.organization
        ).exists():
            return Response(
                {'detail': 'You are already a member of this organization.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Create membership
        membership = Membership.objects.create(
            user=request.user,
            organization=invitation.organization,
            role=invitation.role
        )

        # Mark invitation as accepted
        invitation.accepted_at = timezone.now()
        invitation.save()

        return Response(
            {
                'detail': 'Invitation accepted successfully.',
                'organization': OrganizationSerializer(invitation.organization).data,
                'membership': MembershipSerializer(membership).data
            },
            status=status.HTTP_200_OK
        )

    @action(detail=False, methods=['get'], url_path='my-invitations')
    def my_invitations(self, request, *args, **kwargs):
        """
        List current user's pending invitations across all organizations.
        """
        invitations = Invitation.objects.filter(
            email=request.user.email,
            accepted_at__isnull=True
        ).select_related('organization', 'invited_by').order_by('-created_at')

        # Filter out expired invitations
        valid_invitations = [inv for inv in invitations if inv.can_accept()]

        serializer = InvitationSerializer(valid_invitations, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
