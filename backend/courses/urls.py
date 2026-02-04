from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_nested import routers

from .views import CourseViewSet, DatasetViewSet, EnrollmentViewSet

router = DefaultRouter()
router.register(r'courses', CourseViewSet, basename='course')
router.register(r'enrollments', EnrollmentViewSet, basename='enrollment')

courses_router = routers.NestedDefaultRouter(router, r'courses', lookup='course')
courses_router.register(r'datasets', DatasetViewSet, basename='course-dataset')

urlpatterns = [
    path('', include(router.urls)),
    path('', include(courses_router.urls)),
]
