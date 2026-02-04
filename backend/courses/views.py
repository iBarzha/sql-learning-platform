from rest_framework import viewsets, status, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Count

from .models import Course, Enrollment, Dataset, Lesson
from .serializers import (
    CourseListSerializer,
    CourseDetailSerializer,
    CourseCreateSerializer,
    EnrollmentSerializer,
    EnrollRequestSerializer,
    DatasetSerializer,
    LessonListSerializer,
    LessonDetailSerializer,
    LessonCreateSerializer,
)
from config.permissions import IsInstructor, IsEnrolledOrInstructor, IsCourseInstructor


class CourseViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        queryset = Course.objects.annotate(
            student_count=Count('enrollments', distinct=True),
            assignment_count=Count('assignments', distinct=True),
            lesson_count=Count('lessons', distinct=True)
        )

        if user.is_instructor:
            if self.action == 'list':
                return queryset.filter(instructor=user)
            return queryset
        else:
            if self.action == 'list':
                return queryset.filter(
                    enrollments__student=user,
                    enrollments__status='active'
                )
            return queryset.filter(is_published=True)

    def get_serializer_class(self):
        if self.action == 'list':
            return CourseListSerializer
        if self.action in ['create', 'update', 'partial_update']:
            return CourseCreateSerializer
        return CourseDetailSerializer

    def get_permissions(self):
        if self.action in ['create']:
            return [IsAuthenticated(), IsInstructor()]
        if self.action in ['update', 'partial_update', 'destroy']:
            return [IsAuthenticated(), IsCourseInstructor()]
        return [IsAuthenticated()]

    @action(detail=False, methods=['get'])
    def available(self, request):
        """List available courses for enrollment."""
        enrolled_courses = Enrollment.objects.filter(
            student=request.user
        ).values_list('course_id', flat=True)

        queryset = Course.objects.filter(
            is_published=True
        ).exclude(
            id__in=enrolled_courses
        ).annotate(
            student_count=Count('enrollments', distinct=True)
        )

        serializer = CourseListSerializer(queryset, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def enroll(self, request, pk=None):
        """Enroll in a course."""
        course = self.get_object()

        if Enrollment.objects.filter(student=request.user, course=course).exists():
            return Response(
                {'detail': 'Already enrolled in this course'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if course.enrollment_key:
            serializer = EnrollRequestSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            if serializer.validated_data.get('enrollment_key') != course.enrollment_key:
                return Response(
                    {'detail': 'Invalid enrollment key'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        if course.max_students:
            current_count = course.enrollments.filter(status='active').count()
            if current_count >= course.max_students:
                return Response(
                    {'detail': 'Course is full'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        enrollment = Enrollment.objects.create(student=request.user, course=course)
        return Response(
            EnrollmentSerializer(enrollment).data,
            status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=['post'])
    def unenroll(self, request, pk=None):
        """Unenroll from a course."""
        course = self.get_object()

        try:
            enrollment = Enrollment.objects.get(student=request.user, course=course)
            enrollment.status = 'dropped'
            enrollment.save()
            return Response({'detail': 'Successfully unenrolled'})
        except Enrollment.DoesNotExist:
            return Response(
                {'detail': 'Not enrolled in this course'},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=['get'])
    def students(self, request, pk=None):
        """List students enrolled in the course (instructor only)."""
        course = self.get_object()
        if course.instructor != request.user:
            return Response(
                {'detail': 'Not authorized'},
                status=status.HTTP_403_FORBIDDEN
            )

        enrollments = course.enrollments.select_related('student')
        serializer = EnrollmentSerializer(enrollments, many=True)
        return Response(serializer.data)


class DatasetViewSet(viewsets.ModelViewSet):
    serializer_class = DatasetSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None  # No pagination for datasets

    def get_queryset(self):
        course_id = self.kwargs.get('course_pk')
        return Dataset.objects.filter(course_id=course_id)

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAuthenticated(), IsInstructor()]
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        course_id = self.kwargs.get('course_pk')
        course = Course.objects.get(id=course_id)
        if course.instructor != self.request.user:
            raise PermissionError('Not authorized to add datasets to this course')
        serializer.save(course_id=course_id)


class EnrollmentViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = EnrollmentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_instructor:
            return Enrollment.objects.filter(course__instructor=user)
        return Enrollment.objects.filter(student=user)


class LessonViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        course_id = self.kwargs.get('course_pk')
        user = self.request.user
        queryset = Lesson.objects.filter(course_id=course_id)

        # Students only see published lessons
        if not user.is_instructor:
            queryset = queryset.filter(is_published=True)

        return queryset.order_by('order', 'created_at')

    def get_serializer_class(self):
        if self.action == 'list':
            return LessonListSerializer
        if self.action == 'create':
            return LessonCreateSerializer
        return LessonDetailSerializer

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAuthenticated(), IsInstructor()]
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        course_id = self.kwargs.get('course_pk')
        course = Course.objects.get(id=course_id)
        if course.instructor != self.request.user and not self.request.user.is_superuser:
            raise PermissionError('Not authorized to add lessons to this course')

        # Auto-set order if not provided
        if not serializer.validated_data.get('order'):
            max_order = Lesson.objects.filter(course_id=course_id).count()
            serializer.save(course_id=course_id, order=max_order + 1)
        else:
            serializer.save(course_id=course_id)

    @action(detail=False, methods=['post'])
    def reorder(self, request, course_pk=None):
        """Reorder lessons within a course."""
        lesson_ids = request.data.get('lesson_ids', [])
        for idx, lesson_id in enumerate(lesson_ids):
            Lesson.objects.filter(id=lesson_id, course_id=course_pk).update(order=idx + 1)
        return Response({'detail': 'Lessons reordered successfully'})
