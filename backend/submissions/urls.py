from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import SubmissionViewSet, UserResultViewSet

router = DefaultRouter()
router.register(r'submissions', SubmissionViewSet, basename='submission')
router.register(r'results', UserResultViewSet, basename='result')

urlpatterns = [
    path('', include(router.urls)),
]
