from rest_framework import viewsets, status, views
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from typing import Optional

from .models import Plan, Subscription, Invoice, PaymentMethod
from .serializers import (
    PlanSerializer,
    SubscriptionSerializer,
    InvoiceSerializer,
    PaymentMethodSerializer,
    CreateCheckoutSessionSerializer,
    CancelSubscriptionSerializer
)
from .services import BillingService
from .gateways.base import GatewayException
from organizations.models import Organization
from organizations.permissions import IsOrganizationMember, IsOrganizationAdminOrOwner


class PlanViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing available billing plans.

    list: Returns all active plans
    retrieve: Gets a specific plan by ID
    """
    serializer_class = PlanSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Return only active plans"""
        return Plan.objects.filter(is_active=True).order_by('price_cents')


class SubscriptionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for managing organization subscriptions.

    list: Returns the current subscription for the organization
    retrieve: Gets a specific subscription
    cancel: Cancels a subscription
    """
    serializer_class = SubscriptionSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        """Apply different permissions based on the action"""
        if self.action in ['cancel', 'destroy']:
            return [IsAuthenticated(), IsOrganizationAdminOrOwner()]
        return [IsAuthenticated(), IsOrganizationMember()]

    def get_queryset(self):
        """Return subscriptions for organizations where user is a member"""
        user = self.request.user
        organization_id = self.request.query_params.get('organization_id')

        queryset = Subscription.objects.select_related('plan', 'organization')

        if organization_id:
            # Filter by specific organization (user must be a member)
            queryset = queryset.filter(
                organization_id=organization_id,
                organization__memberships__user=user
            )
        else:
            # Return subscriptions for all organizations user belongs to
            queryset = queryset.filter(
                organization__memberships__user=user
            )

        return queryset.distinct().order_by('-created_at')

    @action(detail=True, methods=['post'], url_path='cancel')
    def cancel(self, request, pk=None):
        """
        Cancel a subscription.

        Request body:
            - cancel_at_period_end (bool): Cancel at period end or immediately
            - reason (str, optional): Reason for cancellation
        """
        subscription = self.get_object()

        # Validate that user has permission for this organization
        if not subscription.organization.memberships.filter(
            user=request.user,
            role__in=['owner', 'admin']
        ).exists():
            return Response(
                {'error': 'You do not have permission to cancel this subscription'},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = CancelSubscriptionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            updated_subscription = BillingService.cancel_subscription(
                subscription=subscription,
                cancel_at_period_end=serializer.validated_data.get('cancel_at_period_end', True),
                reason=serializer.validated_data.get('reason')
            )

            response_serializer = SubscriptionSerializer(updated_subscription)
            return Response(response_serializer.data, status=status.HTTP_200_OK)

        except GatewayException as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=['post'], url_path='sync')
    def sync(self, request, pk=None):
        """
        Sync subscription data from payment gateway.
        """
        subscription = self.get_object()

        try:
            updated_subscription = BillingService.sync_subscription_from_gateway(subscription)
            serializer = SubscriptionSerializer(updated_subscription)
            return Response(serializer.data, status=status.HTTP_200_OK)

        except GatewayException as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class InvoiceViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing invoices.

    list: Returns invoices for organizations where user is a member
    retrieve: Gets a specific invoice
    """
    serializer_class = InvoiceSerializer
    permission_classes = [IsAuthenticated, IsOrganizationMember]

    def get_queryset(self):
        """Return invoices for organizations where user is a member"""
        user = self.request.user
        organization_id = self.request.query_params.get('organization_id')

        queryset = Invoice.objects.select_related('organization', 'subscription')

        if organization_id:
            # Filter by specific organization (user must be a member)
            queryset = queryset.filter(
                organization_id=organization_id,
                organization__memberships__user=user
            )
        else:
            # Return invoices for all organizations user belongs to
            queryset = queryset.filter(
                organization__memberships__user=user
            )

        return queryset.distinct().order_by('-created_at')


class PaymentMethodViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing payment methods.

    list: Returns payment methods for an organization
    retrieve: Gets a specific payment method
    """
    serializer_class = PaymentMethodSerializer
    permission_classes = [IsAuthenticated, IsOrganizationMember]

    def get_queryset(self):
        """Return payment methods for organizations where user is a member"""
        user = self.request.user
        organization_id = self.request.query_params.get('organization_id')

        queryset = PaymentMethod.objects.select_related('organization')

        if organization_id:
            # Filter by specific organization (user must be a member)
            queryset = queryset.filter(
                organization_id=organization_id,
                organization__memberships__user=user
            )
        else:
            # Return payment methods for all organizations user belongs to
            queryset = queryset.filter(
                organization__memberships__user=user
            )

        return queryset.distinct().order_by('-is_default', '-created_at')


class CreateCheckoutSessionView(views.APIView):
    """
    Create a checkout session for subscribing to a plan.

    POST /api/billing/checkout/
    Request body:
        - plan_id (UUID): ID of the plan to subscribe to
        - organization_id (UUID): ID of the organization
        - success_url (str): URL to redirect after successful payment
        - cancel_url (str): URL to redirect after cancelled payment
        - trial_days (int, optional): Number of trial days

    Response:
        - checkout_url (str): URL to redirect user to for payment
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # Get organization and validate membership
        organization_id = request.data.get('organization_id')
        if not organization_id:
            return Response(
                {'error': 'organization_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        organization = get_object_or_404(Organization, id=organization_id)

        # Check if user is a member with admin or owner role
        membership = organization.memberships.filter(
            user=request.user,
            role__in=['owner', 'admin']
        ).first()

        if not membership:
            # Check if user is a member at all
            is_member = organization.memberships.filter(user=request.user).exists()
            if is_member:
                return Response(
                    {'error': 'Only organization owners and admins can create subscriptions'},
                    status=status.HTTP_403_FORBIDDEN
                )
            else:
                return Response(
                    {'error': 'You are not a member of this organization'},
                    status=status.HTTP_403_FORBIDDEN
                )

        # Validate request data
        serializer = CreateCheckoutSessionSerializer(
            data=request.data,
            context={'request': request, 'organization': organization}
        )
        serializer.is_valid(raise_exception=True)

        # Get plan
        plan = get_object_or_404(Plan, id=serializer.validated_data['plan_id'])

        try:
            # Create checkout session
            session_data = BillingService.create_checkout_session(
                organization=organization,
                plan=plan,
                success_url=serializer.validated_data['success_url'],
                cancel_url=serializer.validated_data['cancel_url'],
                metadata={
                    'organization_id': str(organization.id),
                    'organization_name': organization.name,
                    'trial_days': serializer.validated_data.get('trial_days')
                }
            )

            return Response(session_data, status=status.HTTP_200_OK)

        except GatewayException as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class BillingPortalView(views.APIView):
    """
    Get billing portal URL for customer self-service.

    GET /api/billing/portal/?organization_id=<uuid>
    Query params:
        - organization_id (UUID): ID of the organization
        - return_url (str): URL to return to after portal session

    Response:
        - portal_url (str): URL to redirect user to for billing management
    """
    permission_classes = [IsAuthenticated, IsOrganizationMember]

    def get(self, request):
        organization_id = request.query_params.get('organization_id')
        return_url = request.query_params.get('return_url')

        if not organization_id:
            return Response(
                {'error': 'organization_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not return_url:
            return Response(
                {'error': 'return_url is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        organization = get_object_or_404(Organization, id=organization_id)

        # Check if user is a member
        if not organization.memberships.filter(user=request.user).exists():
            return Response(
                {'error': 'You are not a member of this organization'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Get active subscription
        subscription = Subscription.objects.filter(
            organization=organization,
            status__in=['active', 'trialing']
        ).first()

        if not subscription:
            return Response(
                {'error': 'No active subscription found for this organization'},
                status=status.HTTP_404_NOT_FOUND
            )

        try:
            # This method would need to be implemented in BillingService
            # For now, return an error message
            return Response(
                {'error': 'Billing portal is not yet implemented. Please contact support.'},
                status=status.HTTP_501_NOT_IMPLEMENTED
            )

            # Once implemented:
            # portal_url = BillingService.create_billing_portal_url(
            #     subscription=subscription,
            #     return_url=return_url
            # )
            # return Response({'portal_url': portal_url}, status=status.HTTP_200_OK)

        except GatewayException as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
