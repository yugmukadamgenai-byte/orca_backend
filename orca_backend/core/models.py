from django.db import models
from django.contrib.auth.models import User


class Reading(models.Model):
    """One wind/wave data point, pushed from scheduler.py every 3 minutes."""
    timestamp = models.DateTimeField(auto_now_add=True)
    location = models.CharField(max_length=100, db_index=True)
    wind_speed_kmh = models.FloatField(null=True, blank=True)
    wave_height_m = models.FloatField(null=True, blank=True)
    wave_period_s = models.FloatField(null=True, blank=True)
    rain_chance_pct = models.FloatField(null=True, blank=True)

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.location} @ {self.timestamp:%Y-%m-%d %H:%M}"


class AgentRun(models.Model):
    """One real orchestrator.py invocation, pushed after each run."""
    timestamp = models.DateTimeField(auto_now_add=True)
    query = models.TextField()
    location = models.CharField(max_length=100, db_index=True)
    agents_run = models.CharField(max_length=200)  # comma-separated
    verdict = models.CharField(
        max_length=50,
        choices=[
            ("clear", "Clear"),
            ("risk_flagged", "Risk Flagged"),
            ("inconclusive", "Inconclusive"),
            ("unknown", "Unknown"),
        ],
    )
    duration_ms = models.FloatField()
    full_response = models.TextField(blank=True)

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.location} [{self.verdict}] @ {self.timestamp:%Y-%m-%d %H:%M}"


class MobileUserProfile(models.Model):
    """Extends Django's built-in User for mobile app fishermen users.
    Django's User model already gives you username/email/password/auth -
    this just adds the fields specific to ORCA's mobile app."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    phone_number = models.CharField(max_length=20, blank=True)
    preferred_location = models.CharField(max_length=100, blank=True)
    preferred_language = models.CharField(
        max_length=20,
        choices=[
            ("en", "English"), ("ml", "Malayalam"), ("ta", "Tamil"),
            ("te", "Telugu"), ("bn", "Bengali"), ("hi", "Hindi"),
        ],
        default="en",
    )
    boat_registration = models.CharField(max_length=50, blank=True)

    def __str__(self):
        return f"Profile: {self.user.username}"
