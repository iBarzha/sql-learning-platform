"""URL configuration for sandbox app."""

from django.urls import path

from .views import (
    ExecuteQueryView,
    SessionResetView,
    DatabaseTypesView,
    PublicDatasetsView,
    PoolHealthView,
    PoolStatsView,
)

app_name = 'sandbox'

urlpatterns = [
    # Main endpoints
    path('execute/', ExecuteQueryView.as_view(), name='execute-query'),
    path('session/reset/', SessionResetView.as_view(), name='session-reset'),
    path('database-types/', DatabaseTypesView.as_view(), name='database-types'),
    path('datasets/', PublicDatasetsView.as_view(), name='public-datasets'),

    # Health and stats
    path('health/', PoolHealthView.as_view(), name='pool-health'),
    path('stats/', PoolStatsView.as_view(), name='pool-stats'),
]
