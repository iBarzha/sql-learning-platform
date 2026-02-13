from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_nested import routers

from django.conf import settings
from django.conf.urls.static import static

from config.health import health_check, readiness_check

from courses.views import CourseViewSet, DatasetViewSet, EnrollmentViewSet, LessonViewSet, ModuleViewSet, AttachmentViewSet
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
courses_router.register(r'lessons', LessonViewSet, basename='course-lesson')
courses_router.register(r'modules', ModuleViewSet, basename='course-module')

assignments_router = routers.NestedDefaultRouter(courses_router, r'assignments', lookup='assignment')
assignments_router.register(r'submissions', SubmissionViewSet, basename='assignment-submission')
assignments_router.register(r'results', UserResultViewSet, basename='assignment-result')

lessons_router = routers.NestedDefaultRouter(courses_router, r'lessons', lookup='lesson')
lessons_router.register(r'submissions', SubmissionViewSet, basename='lesson-submission')
lessons_router.register(r'attachments', AttachmentViewSet, basename='lesson-attachment')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/health/', health_check),
    path('api/ready/', readiness_check),
    path('api/auth/', include('users.urls')),
    path('api/', include(router.urls)),
    path('api/', include(courses_router.urls)),
    path('api/', include(assignments_router.urls)),
    path('api/', include(lessons_router.urls)),
    path('api/sandbox/', include('sandbox.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
