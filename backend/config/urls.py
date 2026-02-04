from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_nested import routers

from courses.views import CourseViewSet, DatasetViewSet, EnrollmentViewSet
from assignments.views import AssignmentViewSet
from submissions.views import SubmissionViewSet, UserResultViewSet

router = DefaultRouter()
router.register(r'courses', CourseViewSet, basename='course')
router.register(r'enrollments', EnrollmentViewSet, basename='enrollment')
router.register(r'submissions', SubmissionViewSet, basename='submission')
router.register(r'results', UserResultViewSet, basename='result')

courses_router = routers.NestedDefaultRouter(router, r'courses', lookup='course')
courses_router.register(r'datasets', DatasetViewSet, basename='course-dataset')
courses_router.register(r'assignments', AssignmentViewSet, basename='course-assignment')

assignments_router = routers.NestedDefaultRouter(courses_router, r'assignments', lookup='assignment')
assignments_router.register(r'submissions', SubmissionViewSet, basename='assignment-submission')
assignments_router.register(r'results', UserResultViewSet, basename='assignment-result')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include('users.urls')),
    path('api/', include(router.urls)),
    path('api/', include(courses_router.urls)),
    path('api/', include(assignments_router.urls)),
]
