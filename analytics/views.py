
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, viewsets, filters
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone   
from django_filters.rest_framework import DjangoFilterBackend
from .models import Event
from .serializers import (
    TrackEventSerializer, 
    EventSerializer,
)
from . import services
from organizations.models import Organization
from datetime import timedelta

class TrackEventView(APIView):
    """
    Public endpoint to track a new event.
    Can be called using organization API key or user JWT.
    """

    permission_classes = [IsAuthenticated]  

    def post(self, request):
        serializer = TrackEventSerializer(data=request.data)
        if serializer.is_valid():
            data = serializer.validated_data
            event = services.track_event(
                org=data["organization"],
                user=data.get("user"),
                event_name=data["name"],
                properties=data.get("properties"),
                timestamp=data.get("timestamp", timezone.now())
            )
            return Response(EventSerializer(event).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class EventViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Lists events for an organization.
    Supports filtering by user, event name, or date range.
    """
    serializer_class = EventSerializer
    queryset = Event.objects.all()
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["organization", "user", "name"]
    ordering_fields = ["timestamp"]
    ordering = ["-timestamp"]

    def get_queryset(self):
        queryset = super().get_queryset()
        org_id = self.request.query_params.get("org")
        start_date = self.request.query_params.get("start_date")
        end_date = self.request.query_params.get("end_date")

        if org_id:
            queryset = queryset.filter(organization_id=org_id)
        if start_date:
            queryset = queryset.filter(timestamp__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(timestamp__date__lte=end_date)
        
        return queryset

class MetricsView(APIView):
    """
    Returns analytics metrics for an organization between two dates.
    Includes DAU, WAU, MAU, revenue, and top/least-used features.
    """

    def get(self, request):
        from datetime import datetime
        
        org_id = request.query_params.get("org")
        start_date_str = request.query_params.get("start_date")
        end_date_str = request.query_params.get("end_date")

        if not org_id or not start_date_str or not end_date_str:
            return Response({"error": "Missing required parameters."}, status=400)

        org = Organization.objects.get(id=org_id)
        
        # Convert string dates to date objects
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()

        dau = services.get_dau(org, start_date, end_date)
        wau = services.get_wau(org, start_date, end_date)
        mau = services.get_mau(org, start_date, end_date)
        revenue = services.get_revenue_timeseries(org, start_date, end_date)
        top_features = services.get_top_features(org, start_date, end_date)
        least_features = services.get_least_used_features(org, start_date, end_date)

        return Response({
            "dau": dau,
            "wau": wau,
            "mau": mau,
            "revenue": revenue,
            "most_used_features": top_features,
            "least_used_features": least_features,
        })

class DashboardView(APIView):
    """
    Returns a quick summary of recent analytics for dashboard.
    """

    def get(self, request):
        org_id = request.query_params.get("org")
        if not org_id:
            return Response({"error": "Organization ID required."}, status=400)

        org = Organization.objects.get(id=org_id)
        today = timezone.now().date()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)

        dau = services.get_dau(org, today, today)
        wau = services.get_wau(org, week_ago, today)
        mau = services.get_mau(org, month_ago, today)
        revenue = services.get_revenue_timeseries(org, month_ago, today)
        top_features = services.get_top_features(org, start_date=month_ago, end_date=today)
        least_features = services.get_least_used_features(org, start_date=month_ago, end_date=today)

        return Response({
            "organization": org.name,
            "dau_today": dau[-1]["dau"] if dau else 0,
            "wau": wau[-1]["wau"] if wau else 0,
            "mau": mau[-1]["mau"] if mau else 0,
            "total_revenue_cents": sum(r["revenue_cents"] for r in revenue),
            "top_features": top_features,
            "least_features": least_features,
        })