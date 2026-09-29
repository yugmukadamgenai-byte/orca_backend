from rest_framework.routers import DefaultRouter
from django.urls import path, include
from . import views

router = DefaultRouter()
router.register(r"readings", views.ReadingViewSet)
router.register(r"agent-runs", views.AgentRunViewSet)

urlpatterns = [
    path("", include(router.urls)),
    path("trends/", views.trends, name="trends"),
    path("usage-summary/", views.usage_summary, name="usage-summary"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("health/", views.health, name="health"),
    path("login/", views.login_view, name="login"),
    path("register/", views.register_view, name="register"),
    path("pfz/", views.pfz, name="pfz"),
    path("route/", views.route, name="route"),
]
