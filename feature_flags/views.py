"""
Views for feature flag management and evaluation.
"""

from django.db.models import Q
from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from organizations.models import Membership, Organization

from .models import FeatureFlag
from .serializers import FeatureFlagSerializer, UpdateFeatureFlagSerializer
from .services import get_all_flags, is_feature_enabled


class FeatureFlagViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing feature flags.

    list: Returns all flags for an organization (org-specific + global)
    retrieve: Gets a specific flag by key and checks if enabled
    partial_update: Updates a flag for an organization (admin only)
    """

    serializer_class = FeatureFlagSerializer
    lookup_field = "key"
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        """
        Apply different permissions based on the action.
        All actions require authentication.
        Organization membership and admin checks are done in action methods.
        """
        return [IsAuthenticated()]

    def get_queryset(self):
        """
        Return flags for the specified organization plus global flags.
        User must be a member of the organization.
        Note: This is a base queryset; actual filtering is done in action methods.
        """
        organization_id = self.request.query_params.get("organization_id")

        if not organization_id:
            # Return empty queryset if no organization_id provided
            # Validation will happen in action methods
            return FeatureFlag.objects.none()

        # Verify user is a member of the organization
        user = self.request.user
        try:
            organization = Organization.objects.get(
                id=organization_id, memberships__user=user
            )
        except Organization.DoesNotExist:
            return FeatureFlag.objects.none()

        # Get organization-specific flags and global flags
        queryset = FeatureFlag.objects.filter(
            Q(organization=organization) | Q(organization__isnull=True)
        ).distinct()

        return queryset.order_by("-created_at")

    def list(self, request, *args, **kwargs):
        """
        List all feature flags for an organization.
        Returns both organization-specific flags and global flags.
        """
        organization_id = request.query_params.get("organization_id")

        if not organization_id:
            return Response(
                {"error": "organization_id query parameter is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Verify user is a member of the organization
        user = request.user
        try:
            organization = Organization.objects.get(
                id=organization_id, memberships__user=user
            )
        except Organization.DoesNotExist:
            return Response(
                {"error": "Organization not found or you are not a member"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Use service to get all flags
        flags_dict = get_all_flags(organization)

        # Convert to list format for response
        flags_list = []
        for key, flag_data in flags_dict.items():
            # Try to get the actual flag object for full serialization
            flag = FeatureFlag.objects.filter(
                key=key, organization=organization
            ).first()

            if not flag:
                # Get global flag
                flag = FeatureFlag.objects.filter(
                    key=key, organization__isnull=True
                ).first()

            if flag:
                serializer = self.get_serializer(flag)
                flags_list.append(serializer.data)

        return Response(flags_list, status=status.HTTP_200_OK)

    def retrieve(self, request, *args, **kwargs):
        """
        Retrieve a specific feature flag by key and return if it's enabled.
        """
        organization_id = request.query_params.get("organization_id")
        key = kwargs.get("key")

        if not organization_id:
            return Response(
                {"error": "organization_id query parameter is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Verify user is a member of the organization
        user = request.user
        try:
            organization = Organization.objects.get(
                id=organization_id, memberships__user=user
            )
        except Organization.DoesNotExist:
            return Response(
                {"error": "Organization not found or you are not a member"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Check if feature is enabled using service
        enabled = is_feature_enabled(key, organization=organization, user=user)

        # Try to get the flag object for full details
        flag = FeatureFlag.objects.filter(key=key, organization=organization).first()

        if not flag:
            flag = FeatureFlag.objects.filter(
                key=key, organization__isnull=True
            ).first()

        if flag:
            serializer = self.get_serializer(flag)
            data = serializer.data
            data["enabled_for_user"] = enabled
            return Response(data, status=status.HTTP_200_OK)
        # Flag doesn't exist, return default disabled state
        return Response(
            {
                "key": key,
                "enabled": False,
                "enabled_for_user": False,
                "message": "Feature flag not found",
            },
            status=status.HTTP_200_OK,
        )

    def partial_update(self, request, *args, **kwargs):
        """
        Update a feature flag for an organization (admin only).
        Creates an organization-specific override if it doesn't exist.
        """
        organization_id = request.query_params.get("organization_id")
        key = kwargs.get("key")

        if not organization_id:
            return Response(
                {"error": "organization_id query parameter is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Verify user is admin/owner of the organization
        user = request.user
        try:
            organization = Organization.objects.get(
                id=organization_id, memberships__user=user
            )
        except Organization.DoesNotExist:
            return Response(
                {"error": "Organization not found or you are not a member"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Check if user is admin or owner
        try:
            membership = Membership.objects.get(user=user, organization=organization)
            if not membership.is_admin_or_owner():
                return Response(
                    {
                        "error": "Only organization admins and owners can update feature flags"
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )
        except Membership.DoesNotExist:
            return Response(
                {"error": "You are not a member of this organization"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Check if organization-specific flag exists
        org_flag = FeatureFlag.objects.filter(
            key=key, organization=organization
        ).first()

        if not org_flag:
            # Check if global flag exists (to copy defaults)
            global_flag = FeatureFlag.objects.filter(
                key=key, organization__isnull=True
            ).first()

            if not global_flag:
                return Response(
                    {"error": f'Feature flag with key "{key}" does not exist'},
                    status=status.HTTP_404_NOT_FOUND,
                )

            # Create organization-specific override
            org_flag = FeatureFlag.objects.create(
                key=key,
                name=global_flag.name,
                description=global_flag.description,
                default_enabled=global_flag.default_enabled,
                organization=organization,
                enabled=global_flag.enabled,
                rules=global_flag.rules.copy() if global_flag.rules else {},
            )

        # Update the flag
        serializer = UpdateFeatureFlagSerializer(
            org_flag, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(FeatureFlagSerializer(org_flag).data, status=status.HTTP_200_OK)


class EvaluateFeatureView(APIView):
    """
    API endpoint to evaluate if a feature flag is enabled.

    POST /api/feature-flags/evaluate/
    Body: {key: str, org_id: str}
    Returns: {enabled: bool}
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        """
        Evaluate if a feature flag is enabled for an organization.
        """
        key = request.data.get("key")
        org_id = request.data.get("org_id")

        if not key:
            return Response(
                {"error": "key is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        if not org_id:
            return Response(
                {"error": "org_id is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        # Verify user is a member of the organization
        user = request.user
        try:
            organization = Organization.objects.get(id=org_id, memberships__user=user)
        except Organization.DoesNotExist:
            return Response(
                {"error": "Organization not found or you are not a member"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Evaluate feature flag
        enabled = is_feature_enabled(key=key, organization=organization, user=user)

        return Response({"enabled": enabled}, status=status.HTTP_200_OK)
