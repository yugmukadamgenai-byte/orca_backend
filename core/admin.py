from django.contrib import admin
from .models import Reading, AgentRun, MobileUserProfile


@admin.register(Reading)
class ReadingAdmin(admin.ModelAdmin):
    list_display = ("location", "timestamp", "wind_speed_kmh", "wave_height_m", "wave_period_s", "rain_chance_pct")
    list_filter = ("location",)
    date_hierarchy = "timestamp"


@admin.register(AgentRun)
class AgentRunAdmin(admin.ModelAdmin):
    list_display = ("location", "verdict", "timestamp", "duration_ms", "agents_run")
    list_filter = ("location", "verdict")
    search_fields = ("query", "location")
    date_hierarchy = "timestamp"


@admin.register(MobileUserProfile)
class MobileUserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "phone_number", "preferred_location", "preferred_language", "boat_registration")
    search_fields = ("user__username", "phone_number", "boat_registration")
