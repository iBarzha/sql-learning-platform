"""URL configuration for sandbox app."""

from django.urls import path

from .views import (
    PoolStatsView,
    PoolHealthView,
    TestQueryView,
    WarmPoolControlView,
)

app_name = 'sandbox'

urlpatterns = [
    path('health/', PoolHealthView.as_view(), name='pool-health'),
    path('stats/', PoolStatsView.as_view(), name='pool-stats'),
    path('test/', TestQueryView.as_view(), name='test-query'),
    path('control/', WarmPoolControlView.as_view(), name='pool-control'),
]
