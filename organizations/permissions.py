"""
Custom permission classes for organization-level RBAC.

These permissions enforce role-based access control within organizations,
ensuring that only users with appropriate roles can perform specific actions.
"""

from rest_framework import permissions
from .models import Membership


class IsOrganizationOwner(permissions.BasePermission):
    """
    Permission that allows only organization owners to perform the action.

    Used for sensitive operations like deleting organizations or transferring ownership.
    The organization can be accessed via:
    - view.get_object() for detail views
    - view.kwargs['organization_pk'] for nested routes
    """

    message = "Only the organization owner can perform this action."

    def has_permission(self, request, view):
        """
        Check if user is authenticated.
        Object-level check is done in has_object_permission.
        """
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        """
        Check if the user is the owner of the organization.
        Handles both Organization objects and nested objects (Membership, Invitation).
        """
        if not (request.user and request.user.is_authenticated):
            return False

        # Determine the organization object
        from .models import Organization

        if isinstance(obj, Organization):
            organization = obj
        elif hasattr(obj, 'organization'):
            # For Membership, Invitation, etc.
            organization = obj.organization
        else:
            return False

        # Check if user is the owner
        try:
            membership = Membership.objects.get(
                user=request.user,
                organization=organization
            )
            return membership.is_owner()
        except Membership.DoesNotExist:
            return False


class IsOrganizationAdminOrOwner(permissions.BasePermission):
    """
    Permission that allows organization admins and owners to perform the action.

    Used for management operations like inviting members, removing members,
    or viewing sensitive organization data.
    """

    message = "Only organization admins and owners can perform this action."

    def has_permission(self, request, view):
        """
        Check if user is authenticated.
        For nested routes, check if user has admin/owner role in the organization.
        """
        if not (request.user and request.user.is_authenticated):
            return False

        # For nested routes (e.g., /organizations/{id}/members/)
        # Check organization-level permission
        organization_pk = view.kwargs.get('organization_pk')
        if organization_pk:
            try:
                membership = Membership.objects.get(
                    user=request.user,
                    organization_id=organization_pk
                )
                return membership.is_admin_or_owner()
            except Membership.DoesNotExist:
                return False

        return True

    def has_object_permission(self, request, view, obj):
        """
        Check if the user is an admin or owner of the organization.
        Handles both Organization objects and nested objects.
        """
        if not (request.user and request.user.is_authenticated):
            return False

        # Determine the organization object
        from .models import Organization

        if isinstance(obj, Organization):
            organization = obj
        elif hasattr(obj, 'organization'):
            organization = obj.organization
        else:
            return False

        # Check if user is admin or owner
        try:
            membership = Membership.objects.get(
                user=request.user,
                organization=organization
            )
            return membership.is_admin_or_owner()
        except Membership.DoesNotExist:
            return False


class IsOrganizationMember(permissions.BasePermission):
    """
    Permission that allows any organization member to perform the action.

    Used for read operations or actions that any member should be able to perform.
    """

    message = "You must be a member of this organization to perform this action."

    def has_permission(self, request, view):
        """
        Check if user is authenticated.
        For nested routes, check if user is a member of the organization.
        """
        if not (request.user and request.user.is_authenticated):
            return False

        # For nested routes, check membership
        organization_pk = view.kwargs.get('organization_pk')
        if organization_pk:
            return Membership.objects.filter(
                user=request.user,
                organization_id=organization_pk
            ).exists()

        return True

    def has_object_permission(self, request, view, obj):
        """
        Check if the user is a member of the organization.
        Handles both Organization objects and nested objects.
        """
        if not (request.user and request.user.is_authenticated):
            return False

        # Determine the organization object
        from .models import Organization

        if isinstance(obj, Organization):
            organization = obj
        elif hasattr(obj, 'organization'):
            organization = obj.organization
        else:
            return False

        # Check if user is a member
        return Membership.objects.filter(
            user=request.user,
            organization=organization
        ).exists()
