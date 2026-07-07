"""
URL configuration for feature flags app.

Defines API endpoints for:
- Feature Flags (list, retrieve, update by key)
- Feature Flag Evaluation (evaluate if enabled)
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import EvaluateFeatureView, FeatureFlagViewSet

# Create router for feature flag endpoints
router = DefaultRouter()
router.register(r"feature-flags", FeatureFlagViewSet, basename="feature-flag")

urlpatterns = [
    # Standalone evaluation endpoint (must come before router to avoid key conflict)
    # POST /api/feature-flags/evaluate/ - evaluate if feature is enabled
    path(
        "feature-flags/evaluate/",
        EvaluateFeatureView.as_view(),
        name="feature-flag-evaluate",
    ),
    # Include ViewSet routes (list, retrieve, partial_update)
    # GET /api/feature-flags/ - list all flags for organization
    # GET /api/feature-flags/{key}/ - get specific flag by key
    # PATCH /api/feature-flags/{key}/ - update flag for organization
    path("", include(router.urls)),
]
