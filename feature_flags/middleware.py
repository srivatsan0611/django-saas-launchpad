"""
Middleware to inject feature flags into request context.
"""

from organizations.models import Organization

from .services import get_all_flags


class FeatureFlagsMiddleware:
    """
    Middleware that injects feature flags into the request object.

    Adds the following attributes to request:
    - request.feature_flags: Dictionary of all flags for the organization
    - request.organization: Organization object (if available)
    - request.is_feature_enabled(key): Helper method to check if a feature is enabled

    The organization is determined from:
    1. Query parameter 'organization_id'
    2. Request data 'organization_id' or 'org_id'
    3. Session (if available)
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Initialize feature flags context
        request.feature_flags = {}
        request.organization = None

        # Try to get organization ID from various sources
        organization_id = None

        # 1. Try query parameters
        if hasattr(request, "GET"):
            organization_id = request.GET.get("organization_id") or request.GET.get(
                "org_id"
            )

        # 2. Try POST/PUT data (for DRF requests)
        if not organization_id and hasattr(request, "data"):
            organization_id = request.data.get("organization_id") or request.data.get(
                "org_id"
            )

        # 3. Try session (if user is authenticated)
        if (
            not organization_id
            and hasattr(request, "session")
            and hasattr(request, "user")
        ):
            if request.user.is_authenticated:
                # Try to get organization from session
                organization_id = request.session.get("organization_id")

        # 4. Try headers (for API clients)
        if not organization_id and hasattr(request, "META"):
            organization_id = request.META.get("HTTP_X_ORGANIZATION_ID")

        # Get organization and load flags if organization_id is available
        if organization_id:
            try:
                user = (
                    request.user
                    if hasattr(request, "user") and request.user.is_authenticated
                    else None
                )

                if user:
                    # Verify user is a member of the organization
                    organization = Organization.objects.filter(
                        id=organization_id, memberships__user=user
                    ).first()
                else:
                    # For unauthenticated requests, just get the organization
                    organization = Organization.objects.filter(
                        id=organization_id
                    ).first()

                if organization:
                    request.organization = organization
                    # Load all flags for this organization
                    request.feature_flags = get_all_flags(organization)
            except (Organization.DoesNotExist, ValueError):
                # Invalid organization ID, leave flags empty
                pass

        # Add helper method to check if feature is enabled
        def is_feature_enabled(key):
            """
            Check if a feature flag is enabled for the current request context.

            Args:
                key: Feature flag key

            Returns:
                bool: True if enabled, False otherwise
            """
            if not request.organization:
                return False

            flag_data = request.feature_flags.get(key)
            if flag_data is None:
                return False

            # For middleware, we return the base enabled state
            # User-specific rules (rollout, whitelist) should be checked in views/decorators
            return flag_data.get("enabled", False)

        request.is_feature_enabled = is_feature_enabled

        # Process the request
        response = self.get_response(request)

        return response
