"""
Decorators for feature flag enforcement in views.
"""

from functools import wraps

from rest_framework import status
from rest_framework.response import Response

from organizations.models import Organization

from .services import is_feature_enabled


def require_feature(key, organization_param="organization_id"):
    """
    Decorator to require a feature flag to be enabled for a view.

    Returns 403 Forbidden if the feature is disabled for the organization.

    Usage:
        @require_feature('new_dashboard')
        def my_view(request):
            ...

    For class-based views:
        @method_decorator(require_feature('new_dashboard'))
        def get(self, request):
            ...

    Args:
        key: Feature flag key to check
        organization_param: Query parameter name for organization ID (default: 'organization_id')

    Returns:
        Decorated function that checks feature flag before executing
    """

    def decorator(func):
        @wraps(func)
        def wrapper(request, *args, **kwargs):
            # Get organization ID from query parameters or request data
            organization_id = None

            # Try query parameters first
            if hasattr(request, "query_params"):
                organization_id = request.query_params.get(organization_param)

            # Try GET parameters (for regular Django views)
            if not organization_id and hasattr(request, "GET"):
                organization_id = request.GET.get(organization_param)

            # Try POST/PUT data
            if not organization_id and hasattr(request, "data"):
                organization_id = request.data.get(organization_param)

            # Try from middleware context if available
            if hasattr(request, "organization") and request.organization:
                organization = request.organization
            else:
                # Get organization from ID
                if not organization_id:
                    return Response(
                        {
                            "error": f"{organization_param} is required",
                            "detail": f'Feature flag "{key}" requires an organization context',
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                # Verify user is a member of the organization
                user = (
                    request.user
                    if hasattr(request, "user") and request.user.is_authenticated
                    else None
                )

                try:
                    if user:
                        organization = Organization.objects.get(
                            id=organization_id, memberships__user=user
                        )
                    else:
                        # For unauthenticated requests, just get the organization
                        organization = Organization.objects.get(id=organization_id)
                except Organization.DoesNotExist:
                    return Response(
                        {
                            "error": "Organization not found",
                            "detail": f'Feature flag "{key}" check failed: organization not found',
                        },
                        status=status.HTTP_404_NOT_FOUND,
                    )

            # Check if feature is enabled
            user = (
                request.user
                if hasattr(request, "user") and request.user.is_authenticated
                else None
            )
            enabled = is_feature_enabled(key=key, organization=organization, user=user)

            if not enabled:
                return Response(
                    {
                        "error": "Feature not enabled",
                        "detail": f'Feature flag "{key}" is not enabled for this organization',
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

            # Feature is enabled, proceed with the view
            return func(request, *args, **kwargs)

        return wrapper

    return decorator
