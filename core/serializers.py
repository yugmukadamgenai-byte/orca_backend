from rest_framework import serializers
from .models import Reading, AgentRun, MobileUserProfile


class ReadingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Reading
        fields = "__all__"
        read_only_fields = ["timestamp"]


class AgentRunSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgentRun
        fields = "__all__"
        read_only_fields = ["timestamp"]


class MobileUserProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = MobileUserProfile
        fields = ["username", "phone_number", "preferred_location", "preferred_language", "boat_registration"]
