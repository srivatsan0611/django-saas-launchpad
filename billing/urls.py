"""
URL configuration for billing app.

Defines API endpoints for:
- Plans (read-only)
- Subscriptions (with cancel/sync actions)
- Invoices (read-only)
- Payment Methods (read-only)
- Checkout session creation
- Billing portal
- Webhooks
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    PlanViewSet,
    SubscriptionViewSet,
    InvoiceViewSet,
    PaymentMethodViewSet,
    CreateCheckoutSessionView,
    BillingPortalView,
)
from .webhooks import handle_razorpay_webhook, handle_generic_webhook


# Create router for viewsets
router = DefaultRouter()
router.register(r'plans', PlanViewSet, basename='plan')
router.register(r'subscriptions', SubscriptionViewSet, basename='subscription')
router.register(r'invoices', InvoiceViewSet, basename='invoice')
router.register(r'payment-methods', PaymentMethodViewSet, basename='paymentmethod')

urlpatterns = [
    # ViewSet endpoints (plans, subscriptions, invoices, payment-methods)
    path('', include(router.urls)),

    # Checkout and billing portal
    path(
        'checkout/',
        CreateCheckoutSessionView.as_view(),
        name='billing-checkout'
    ),
    path(
        'portal/',
        BillingPortalView.as_view(),
        name='billing-portal'
    ),

    # Webhook endpoints
    path(
        'webhooks/razorpay/',
        handle_razorpay_webhook,
        name='webhook-razorpay'
    ),
    path(
        'webhooks/<str:gateway_name>/',
        handle_generic_webhook,
        name='webhook-generic'
    ),
]
