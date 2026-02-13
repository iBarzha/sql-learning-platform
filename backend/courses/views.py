import os

from django.db import transaction
from django.db.models import Count, Exists, Max, OuterRef, Prefetch
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser

from assignments.models import Assignment
from .models import Course, Enrollment, Dataset, Lesson, Module, Attachment
from .serializers import (
    CourseListSerializer,
    CourseDetailSerializer,
    CourseCreateSerializer,
    EnrollmentSerializer,
    JoinByCodeSerializer,
    DatasetSerializer,
    LessonListSerializer,
    LessonDetailSerializer,
    LessonCreateSerializer,
    ModuleListSerializer,
    ModuleDetailSerializer,
    ModuleCreateSerializer,
    AttachmentSerializer,
)
from config.permissions import IsInstructor, IsCourseInstructor


class CourseViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        queryset = Course.objects.annotate(
            student_count=Count('enrollments', distinct=True),
            assignment_count=Count('assignments', distinct=True),
            lesson_count=Count('lessons', distinct=True),
            is_enrolled=Exists(
                Enrollment.objects.filter(
                    course=OuterRef('pk'),
                    student=user,
                    status='active',
                )
            ),
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
            student_count=Count('enrollments', distinct=True),
            assignment_count=Count('assignments', distinct=True),
            lesson_count=Count('lessons', distinct=True),
            is_enrolled=Exists(
                Enrollment.objects.filter(
                    course=OuterRef('pk'),
                    student=request.user,
                    status='active',
                )
            ),
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

    @action(detail=False, methods=['post'], url_path='join')
    def join_by_code(self, request):
        """Join a course by its course code."""
        serializer = JoinByCodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        code = serializer.validated_data['code'].upper()

        try:
            course = Course.objects.get(course_code=code)
        except Course.DoesNotExist:
            return Response(
                {'detail': 'Invalid course code'},
                status=status.HTTP_404_NOT_FOUND
            )

        if not course.is_published:
            return Response(
                {'detail': 'This course is not available'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if Enrollment.objects.filter(student=request.user, course=course).exists():
            return Response(
                {'detail': 'Already enrolled in this course'},
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
        # Return course data along with enrollment
        course_data = CourseDetailSerializer(
            Course.objects.annotate(
                student_count=Count('enrollments', distinct=True),
                assignment_count=Count('assignments', distinct=True),
                lesson_count=Count('lessons', distinct=True),
                is_enrolled=Exists(
                    Enrollment.objects.filter(
                        course=OuterRef('pk'),
                        student=request.user,
                        status='active',
                    )
                ),
            ).get(pk=course.pk),
            context={'request': request}
        ).data
        return Response(course_data, status=status.HTTP_201_CREATED)

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

    @action(detail=True, methods=['post'])
    def duplicate(self, request, pk=None):
        """Deep-copy a course: modules, lessons, datasets, assignments."""
        course = self.get_object()
        if course.instructor != request.user:
            return Response(
                {'detail': 'Not authorized'},
                status=status.HTTP_403_FORBIDDEN
            )

        new_title = request.data.get('title', f'{course.title} (Copy)')
        if not new_title or not str(new_title).strip():
            return Response(
                {'detail': 'Title cannot be empty'},
                status=status.HTTP_400_BAD_REQUEST
            )
        new_title = str(new_title).strip()[:255]

        with transaction.atomic():
            # Clone course (course_code auto-generated in save())
            new_course = Course.objects.create(
                title=new_title,
                description=course.description,
                instructor=request.user,
                database_type=course.database_type,
                is_published=False,
                max_students=course.max_students,
            )

            # Map old IDs -> new objects for FK references
            dataset_map = {}
            module_map = {}

            # Clone datasets
            for ds in course.datasets.all():
                old_id = ds.id
                new_ds = Dataset.objects.create(
                    name=ds.name,
                    description=ds.description,
                    course=new_course,
                    database_type=ds.database_type,
                    schema_sql=ds.schema_sql,
                    seed_sql=ds.seed_sql,
                    is_default=ds.is_default,
                )
                dataset_map[old_id] = new_ds

            # Clone modules
            for mod in course.modules.all():
                old_id = mod.id
                new_mod = Module.objects.create(
                    course=new_course,
                    title=mod.title,
                    description=mod.description,
                    order=mod.order,
                    is_published=mod.is_published,
                )
                module_map[old_id] = new_mod

            # Clone lessons
            for lesson in course.lessons.all():
                Lesson.objects.create(
                    course=new_course,
                    module=module_map.get(lesson.module_id),
                    title=lesson.title,
                    description=lesson.description,
                    lesson_type=lesson.lesson_type,
                    order=lesson.order,
                    theory_content=lesson.theory_content,
                    practice_description=lesson.practice_description,
                    practice_initial_code=lesson.practice_initial_code,
                    expected_query=lesson.expected_query,
                    expected_result=lesson.expected_result,
                    required_keywords=lesson.required_keywords,
                    forbidden_keywords=lesson.forbidden_keywords,
                    order_matters=lesson.order_matters,
                    max_score=lesson.max_score,
                    time_limit_seconds=lesson.time_limit_seconds,
                    max_attempts=lesson.max_attempts,
                    hints=lesson.hints,
                    dataset=dataset_map.get(lesson.dataset_id),
                    is_published=lesson.is_published,
                )

            # Clone assignments
            for asn in Assignment.objects.filter(course=course):
                Assignment.objects.create(
                    course=new_course,
                    module=module_map.get(asn.module_id),
                    dataset=dataset_map.get(asn.dataset_id),
                    title=asn.title,
                    description=asn.description,
                    instructions=asn.instructions,
                    query_type=asn.query_type,
                    difficulty=asn.difficulty,
                    expected_query=asn.expected_query,
                    expected_result=asn.expected_result,
                    required_keywords=asn.required_keywords,
                    forbidden_keywords=asn.forbidden_keywords,
                    order_matters=asn.order_matters,
                    partial_match=asn.partial_match,
                    max_score=asn.max_score,
                    time_limit_seconds=asn.time_limit_seconds,
                    max_attempts=asn.max_attempts,
                    hints=asn.hints,
                    is_published=asn.is_published,
                    order=asn.order,
                )

        serializer = CourseDetailSerializer(new_course, context={'request': request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)

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

    def get_queryset(self):
        course_id = self.kwargs.get('course_pk')
        user = self.request.user
        queryset = Dataset.objects.filter(course_id=course_id)

        # Restrict access: instructor of this course or enrolled student
        if not user.is_instructor:
            queryset = queryset.filter(
                course__enrollments__student=user,
                course__enrollments__status='active',
            )
        elif not user.is_superuser:
            queryset = queryset.filter(course__instructor=user)

        return queryset.distinct()

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAuthenticated(), IsInstructor()]
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        course_id = self.kwargs.get('course_pk')
        try:
            course = Course.objects.get(id=course_id)
        except Course.DoesNotExist:
            raise NotFound('Course not found')
        if course.instructor != self.request.user:
            raise PermissionDenied('Not authorized to add datasets to this course')
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
        from submissions.models import UserResult

        course_id = self.kwargs.get('course_pk')
        user = self.request.user
        queryset = Lesson.objects.filter(course_id=course_id)

        # Students only see published lessons
        if not user.is_instructor:
            queryset = queryset.filter(is_published=True)

        # Prefetch user results for the current user to avoid N+1 in serializers
        if user.is_authenticated:
            queryset = queryset.prefetch_related(
                Prefetch(
                    'user_results',
                    queryset=UserResult.objects.filter(student=user),
                    to_attr='_prefetched_user_results',
                )
            )

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
        try:
            course = Course.objects.get(id=course_id)
        except Course.DoesNotExist:
            raise NotFound('Course not found')
        if course.instructor != self.request.user and not self.request.user.is_superuser:
            raise PermissionDenied('Not authorized to add lessons to this course')

        # Auto-set order if not provided
        if not serializer.validated_data.get('order'):
            max_order = Lesson.objects.filter(course_id=course_id).aggregate(Max('order'))['order__max'] or 0
            serializer.save(course_id=course_id, order=max_order + 1)
        else:
            serializer.save(course_id=course_id)

    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated, IsInstructor])
    def reorder(self, request, course_pk=None):
        """Reorder lessons within a course.

        Request body: {"lesson_ids": ["uuid1", "uuid2", ...]}
        """
        try:
            course = Course.objects.get(id=course_pk)
        except Course.DoesNotExist:
            return Response({'detail': 'Course not found'}, status=status.HTTP_404_NOT_FOUND)
        if course.instructor != request.user and not request.user.is_superuser:
            return Response({'detail': 'Not authorized'}, status=status.HTTP_403_FORBIDDEN)

        lesson_ids = request.data.get('lesson_ids', [])
        for idx, lesson_id in enumerate(lesson_ids):
            Lesson.objects.filter(id=lesson_id, course_id=course_pk).update(order=idx + 1)
        return Response({'detail': 'Lessons reordered successfully'})


class ModuleViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    pagination_class = None

    def get_queryset(self):
        course_id = self.kwargs.get('course_pk')
        user = self.request.user
        queryset = Module.objects.filter(course_id=course_id).annotate(
            lesson_count=Count('lessons', distinct=True)
        )
        if not user.is_instructor:
            queryset = queryset.filter(is_published=True)
        return queryset.order_by('order', 'created_at')

    def get_serializer_class(self):
        if self.action == 'list':
            return ModuleListSerializer
        if self.action == 'create':
            return ModuleCreateSerializer
        return ModuleDetailSerializer

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAuthenticated(), IsInstructor()]
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        course_id = self.kwargs.get('course_pk')
        try:
            course = Course.objects.get(id=course_id)
        except Course.DoesNotExist:
            raise NotFound('Course not found')
        if course.instructor != self.request.user and not self.request.user.is_superuser:
            raise PermissionDenied('Not authorized')

        if not serializer.validated_data.get('order'):
            max_order = Module.objects.filter(
                course_id=course_id
            ).aggregate(Max('order'))['order__max'] or 0
            serializer.save(course_id=course_id, order=max_order + 1)
        else:
            serializer.save(course_id=course_id)

    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated, IsInstructor])
    def reorder(self, request, course_pk=None):
        """Reorder modules within a course.

        Request body: {"module_ids": ["uuid1", "uuid2", ...]}
        """
        try:
            course = Course.objects.get(id=course_pk)
        except Course.DoesNotExist:
            return Response({'detail': 'Course not found'}, status=status.HTTP_404_NOT_FOUND)
        if course.instructor != request.user and not request.user.is_superuser:
            return Response({'detail': 'Not authorized'}, status=status.HTTP_403_FORBIDDEN)

        module_ids = request.data.get('module_ids', [])
        for idx, module_id in enumerate(module_ids):
            Module.objects.filter(
                id=module_id, course_id=course_pk
            ).update(order=idx + 1)
        return Response({'detail': 'Modules reordered successfully'})


EXTENSION_TO_TYPE = {
    '.pdf': 'pdf',
    '.png': 'image', '.jpg': 'image', '.jpeg': 'image',
    '.gif': 'image', '.svg': 'image', '.webp': 'image',
    '.sql': 'code', '.py': 'code', '.js': 'code', '.ts': 'code',
    '.json': 'code', '.csv': 'code', '.xml': 'code',
}


class AttachmentViewSet(viewsets.ModelViewSet):
    serializer_class = AttachmentSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    pagination_class = None
    http_method_names = ['get', 'post', 'delete', 'head', 'options']

    def get_queryset(self):
        lesson_pk = self.kwargs.get('lesson_pk')
        return Attachment.objects.filter(
            lesson_id=lesson_pk,
        ).select_related('uploaded_by')

    def get_permissions(self):
        if self.action in ['create', 'destroy']:
            return [IsAuthenticated(), IsInstructor()]
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        lesson_pk = self.kwargs.get('lesson_pk')
        course_pk = self.kwargs.get('course_pk')

        try:
            lesson = Lesson.objects.select_related('course').get(
                id=lesson_pk, course_id=course_pk,
            )
        except Lesson.DoesNotExist:
            raise NotFound('Lesson not found')

        if lesson.course.instructor != self.request.user:
            raise PermissionDenied('Not authorized')

        uploaded_file = self.request.FILES.get('file')
        if not uploaded_file:
            raise ValidationError({'file': 'No file uploaded.'})

        ext = os.path.splitext(uploaded_file.name)[1].lower()
        allowed_extensions = set(EXTENSION_TO_TYPE.keys()) | {'.txt', '.md', '.docx', '.xlsx'}
        if ext not in allowed_extensions:
            raise ValidationError({
                'file': f'File type "{ext}" is not allowed. '
                        f'Allowed: {", ".join(sorted(allowed_extensions))}'
            })
        file_type = EXTENSION_TO_TYPE.get(ext, 'other')

        serializer.save(
            lesson=lesson,
            uploaded_by=self.request.user,
            filename=uploaded_file.name,
            file_type=file_type,
            file_size=uploaded_file.size,
        )
