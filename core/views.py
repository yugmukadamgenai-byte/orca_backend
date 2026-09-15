from django.conf import settings
from django.db.models import Avg
from django.utils import timezone
from datetime import timedelta

from rest_framework import viewsets, permissions
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import Reading, AgentRun
from .serializers import ReadingSerializer, AgentRunSerializer


class PushKeyOrReadOnly(permissions.BasePermission):
    """GET requests (for the mobile app / dashboard) are open. POST requests
    (pushing new data from your local PC's scheduler.py / orchestrator.py)
    require the shared secret in the X-API-KEY header, so random people on
    the internet can't write fake data into your database."""

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.headers.get("X-API-KEY") == settings.PUSH_API_KEY


class ReadingViewSet(viewsets.ModelViewSet):
    queryset = Reading.objects.all()
    serializer_class = ReadingSerializer
    permission_classes = [PushKeyOrReadOnly]

    def get_queryset(self):
        qs = super().get_queryset()
        location = self.request.query_params.get("location")
        if location:
            qs = qs.filter(location__iexact=location)
        return qs


class AgentRunViewSet(viewsets.ModelViewSet):
    queryset = AgentRun.objects.all()
    serializer_class = AgentRunSerializer
    permission_classes = [PushKeyOrReadOnly]


@api_view(["GET"])
def trends(request):
    """Aggregated wind/wave trends for charting - e.g.
    /api/trends/?location=Kochi&timeframe=week
    Mirrors the day/week/month/year buckets the dashboard needs."""
    location = request.query_params.get("location")
    timeframe = request.query_params.get("timeframe", "day")

    lookback = {
        "day": timedelta(days=1),
        "week": timedelta(days=7),
        "month": timedelta(days=30),
        "year": timedelta(days=365),
    }.get(timeframe, timedelta(days=1))

    qs = Reading.objects.filter(timestamp__gte=timezone.now() - lookback)
    if location:
        qs = qs.filter(location__iexact=location)

    data = list(
        qs.order_by("timestamp").values(
            "timestamp", "wind_speed_kmh", "wave_height_m", "wave_period_s", "rain_chance_pct"
        )
    )
    return Response({"location": location, "timeframe": timeframe, "count": len(data), "readings": data})


@api_view(["GET"])
def usage_summary(request):
    """Quick summary stats for the agent usage view - counts, avg duration,
    verdict breakdown."""
    qs = AgentRun.objects.all()
    total = qs.count()
    avg_duration = qs.aggregate(avg=Avg("duration_ms"))["avg"] or 0

    verdict_counts = {}
    for verdict in qs.values_list("verdict", flat=True):
        verdict_counts[verdict] = verdict_counts.get(verdict, 0) + 1

    return Response({
        "total_runs": total,
        "avg_duration_ms": round(avg_duration, 1),
        "verdict_counts": verdict_counts,
    })
