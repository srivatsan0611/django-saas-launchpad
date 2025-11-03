"""
URL configuration for organizations app.

Defines API endpoints for:
- Organizations (CRUD)
- Memberships (nested under organizations)
- Invitations (nested under organizations, plus standalone endpoints)
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import OrganizationViewSet, MembershipViewSet, InvitationViewSet


# Create router for top-level organization endpoints
router = DefaultRouter()
router.register(r'organizations', OrganizationViewSet, basename='organization')

# Nested routes are defined manually below
# Pattern: /api/organizations/{org_id}/members/
# Pattern: /api/organizations/{org_id}/invitations/

urlpatterns = [
    # Organization CRUD endpoints
    path('', include(router.urls)),

    # Nested Membership endpoints
    path(
        'organizations/<uuid:organization_pk>/members/',
        MembershipViewSet.as_view({
            'get': 'list',
        }),
        name='organization-members-list'
    ),
    path(
        'organizations/<uuid:organization_pk>/members/<int:pk>/',
        MembershipViewSet.as_view({
            'get': 'retrieve',
            'delete': 'destroy',
        }),
        name='organization-members-detail'
    ),
    path(
        'organizations/<uuid:organization_pk>/members/<int:pk>/change-role/',
        MembershipViewSet.as_view({
            'post': 'change_role',
        }),
        name='organization-members-change-role'
    ),

    # Nested Invitation endpoints
    path(
        'organizations/<uuid:organization_pk>/invitations/',
        InvitationViewSet.as_view({
            'get': 'list',
            'post': 'create',
        }),
        name='organization-invitations-list'
    ),
    path(
        'organizations/<uuid:organization_pk>/invitations/<uuid:pk>/',
        InvitationViewSet.as_view({
            'get': 'retrieve',
            'delete': 'destroy',
        }),
        name='organization-invitations-detail'
    ),
    path(
        'organizations/<uuid:organization_pk>/invitations/accept/',
        InvitationViewSet.as_view({
            'post': 'accept_invitation',
        }),
        name='organization-invitations-accept'
    ),

    # Standalone invitation endpoint (not organization-specific)
    path(
        'invitations/my-invitations/',
        InvitationViewSet.as_view({
            'get': 'my_invitations',
        }),
        name='my-invitations'
    ),
]
