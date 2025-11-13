# analytics/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
     EventViewSet,
     TrackEventView, 
     MetricsView
)
router = DefaultRouter()
router.register(r'events', EventViewSet, basename='event')

urlpatterns = [
    # Event tracking endpoint
    path('track/', TrackEventView.as_view(), name='track-event'),

    # Analytics metrics 
    path('metrics/', MetricsView.as_view(), name='metrics'),

    # Include all ViewSets (like /events/)
    path('', include(router.urls)),
]
