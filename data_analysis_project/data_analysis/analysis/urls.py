

# analysis/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # Your main dashboard (home page)
    path("", views.dashboard, name="dashboard"),

    # Database (full page is still available, but we won’t navigate to it)
    path("database/", views.database_dashboard, name="database_dashboard"),
    path("database/panel/", views.database_panel, name="database_panel"),

    # CRUD (EconomicIndicator)
    path("database/indicator/add/", views.indicator_create, name="indicator_add"),
    path("database/indicator/<int:year>/edit/", views.indicator_update, name="indicator_edit"),
    path("database/indicator/<int:year>/delete/", views.indicator_delete, name="indicator_delete"),

    # Chart JSON
    path("api/series/economic/", views.series_economic, name="api_series_economic"),

    # CSV export
    path("database/export/economic.csv",            views.export_economic_csv,          name="export_economic_csv"),
    path("database/export/volatility.csv",          views.export_volatility_csv,        name="export_volatility_csv"),
    path("database/export/brics.csv",               views.export_brics_csv,             name="export_brics_csv"),
    path("database/export/stats.csv",               views.export_stats_csv,             name="export_stats_csv"),
    path("database/export/performance_summary.csv", views.export_performance_summary_csv, name="export_performance_summary_csv"),

    # CSV import
    path("database/import/csv/", views.import_csv, name="import_csv"),

    # JSON API you already expose
    path("api/apartheid-comparison/", views.apartheid_comparison),
    path("api/high-volatility/",      views.high_volatility_years),
    path("api/performance-summary/",  views.performance_summary),
    path("api/recent-trends/",        views.recent_trends),
    path("api/outliers/",             views.outlier_years),
    path("api/avg-by-era/",           views.avg_by_era),
]


