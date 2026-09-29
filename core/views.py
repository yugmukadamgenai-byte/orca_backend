from pathlib import Path

from django.conf import settings
from django.http import HttpResponse
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from django.db.models import Avg
from django.utils import timezone
from datetime import timedelta

from rest_framework import viewsets, permissions, status
from rest_framework.decorators import api_view, action
from rest_framework.response import Response
from rest_framework.authtoken.models import Token

from .models import Reading, AgentRun, MobileUserProfile
from .serializers import ReadingSerializer, AgentRunSerializer, MobileUserProfileSerializer


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

    def get_queryset(self):
        qs = super().get_queryset()
        location = self.request.query_params.get("location")
        if location:
            qs = qs.filter(location__iexact=location)
        return qs

    @action(detail=False, methods=["get"])
    def latest(self, request):
        """GET /api/agent-runs/latest/?location=Kochi
        Returns just the single most recent run for that area - the one
        call a mobile app's home screen actually needs, instead of
        fetching a paginated list and taking results[0] itself."""
        location = request.query_params.get("location")
        if not location:
            return Response({"error": "location query parameter is required"}, status=status.HTTP_400_BAD_REQUEST)

        run = AgentRun.objects.filter(location__iexact=location).order_by("-timestamp").first()
        if not run:
            return Response({"error": f"No agent runs found for '{location}'"}, status=status.HTTP_404_NOT_FOUND)

        return Response(AgentRunSerializer(run).data)


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


@api_view(["POST"])
def register_view(request):
    """POST /api/register/
    Body: {
        "username": "...", "password": "...",
        "phone_number": "..." (optional),
        "preferred_location": "..." (optional),
        "preferred_language": "en" (optional, one of en/ml/ta/te/bn/hi),
        "boat_registration": "..." (optional)
    }

    Creates a new user + profile and returns a token immediately (the app
    can treat successful registration as an automatic login - no separate
    call needed)."""
    username = request.data.get("username")
    password = request.data.get("password")

    if not username or not password:
        return Response(
            {"error": "Both username and password are required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        validate_password(password)
    except DjangoValidationError as e:
        return Response({"error": list(e.messages)}, status=status.HTTP_400_BAD_REQUEST)

    try:
        user = User.objects.create_user(username=username, password=password)
    except IntegrityError:
        return Response(
            {"error": f"Username '{username}' is already taken."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    profile = MobileUserProfile.objects.create(
        user=user,
        phone_number=request.data.get("phone_number", ""),
        preferred_location=request.data.get("preferred_location", ""),
        preferred_language=request.data.get("preferred_language", "en"),
        boat_registration=request.data.get("boat_registration", ""),
    )

    token = Token.objects.create(user=user)

    return Response(
        {
            "token": token.key,
            "username": user.username,
            "profile": MobileUserProfileSerializer(profile).data,
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["POST"])
def login_view(request):
    """POST /api/login/
    Body: {"username": "...", "password": "..."}

    Returns a token the app should send on every subsequent request as:
        Authorization: Token <token>

    NOTE: this only works for accounts that already exist (created via
    Django admin for now) - there is no self-registration endpoint yet.
    That's a separate, deliberately not-yet-built piece - ask backend to
    add a /api/register/ endpoint when you're ready to let users sign up
    from the app itself, rather than needing an admin to create accounts.
    """
    username = request.data.get("username")
    password = request.data.get("password")

    if not username or not password:
        return Response(
            {"error": "Both username and password are required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    user = authenticate(username=username, password=password)
    if not user:
        return Response(
            {"error": "Invalid username or password."},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    token, _ = Token.objects.get_or_create(user=user)

    profile_data = None
    try:
        profile_data = MobileUserProfileSerializer(user.profile).data
    except MobileUserProfile.DoesNotExist:
        pass  # user exists but hasn't filled in a profile yet - that's fine

    return Response({
        "token": token.key,
        "username": user.username,
        "profile": profile_data,
    })


@api_view(["GET"])
def pfz(request):
    """GET /api/pfz/?location=Kochi
    Returns just the structured fishing zone data from the most recent
    agent run for that location - clean lat/lon per zone, ready for the
    app to plot directly, without needing to parse full_response text
    or fetch the whole agent-run record."""
    location = request.query_params.get("location")
    if not location:
        return Response({"error": "location query parameter is required"}, status=status.HTTP_400_BAD_REQUEST)

    run = AgentRun.objects.filter(location__iexact=location).order_by("-timestamp").first()
    if not run:
        return Response({"error": f"No data found for '{location}'"}, status=status.HTTP_404_NOT_FOUND)

    return Response({
        "location": location,
        "timestamp": run.timestamp,
        "zones": run.pfz_zones,
    })


@api_view(["GET"])
def route(request):
    """GET /api/route/?location=Kochi
    Returns the optimized visiting order for that location's fishing
    zones - waypoints (with lat/lon and per-leg distance) and total
    trip distance, from the most recent agent run."""
    location = request.query_params.get("location")
    if not location:
        return Response({"error": "location query parameter is required"}, status=status.HTTP_400_BAD_REQUEST)

    run = AgentRun.objects.filter(location__iexact=location).order_by("-timestamp").first()
    if not run:
        return Response({"error": f"No data found for '{location}'"}, status=status.HTTP_404_NOT_FOUND)

    return Response({
        "location": location,
        "timestamp": run.timestamp,
        **run.route_data,
    })


@api_view(["GET"])
def health(request):
    """Simple uptime/monitoring endpoint - returns 200 with no database
    query, so it works even if Neon is temporarily unreachable, letting
    you tell 'the web service is up' apart from 'the database is down'
    as two different failure modes."""
    return Response({"status": "ok"})


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


def dashboard(request):
    """GET /api/dashboard/ - the ORCA web dashboard (single HTML page that
    calls the JSON endpoints above from the browser)."""
    html = (Path(__file__).parent / "templates" / "core" / "dashboard.html").read_text(encoding="utf-8")
    return HttpResponse(html)
