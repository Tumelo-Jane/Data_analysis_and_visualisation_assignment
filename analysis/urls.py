from django.urls import path
from . import views

app_name = "analysis"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("database/", views.database, name="database"),
    path("api/metrics/", views.metrics_api, name="metrics_api"),
]
