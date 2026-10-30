import os

from django.db import transaction
from django.db.models import Count, Exists, Max, OuterRef, Prefetch, Q
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser

from assignments.models import Assignment
from .models import Course, Enrollment, Dataset, Lesson, LessonExercise, Module, Attachment
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
from config.permissions import IsInstructor, IsCourseInstructor, require_course_manager


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
                if user.is_superuser or getattr(user, 'role', None) == 'admin':
                    return queryset
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

        existing = Enrollment.objects.filter(student=request.user, course=course).first()
        if existing and existing.status != Enrollment.Status.DROPPED:
            return Response(
                {'detail': 'Already enrolled in this course'},
                status=status.HTTP_400_BAD_REQUEST
            )

        with transaction.atomic():
            # Lock the course row to prevent concurrent over-enrollment
            course = Course.objects.select_for_update().get(pk=course.pk)
            if course.max_students:
                current_count = course.enrollments.filter(status='active').count()
                if current_count >= course.max_students:
                    return Response(
                        {'detail': 'Course is full'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            if existing:
                # A dropped student is rejoining; the unique (student, course) row is reused.
                existing.status = Enrollment.Status.ACTIVE
                existing.completed_at = None
                existing.save(update_fields=['status', 'completed_at'])
                enrollment = existing
            else:
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

        existing = Enrollment.objects.filter(student=request.user, course=course).first()
        if existing and existing.status != Enrollment.Status.DROPPED:
            return Response(
                {'detail': 'Already enrolled in this course'},
                status=status.HTTP_400_BAD_REQUEST
            )

        with transaction.atomic():
            # Lock the course row to prevent concurrent over-enrollment
            course = Course.objects.select_for_update().get(pk=course.pk)
            if course.max_students:
                current_count = course.enrollments.filter(status='active').count()
                if current_count >= course.max_students:
                    return Response(
                        {'detail': 'Course is full'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            if existing:
                # A dropped student is rejoining; the unique (student, course) row is reused.
                existing.status = Enrollment.Status.ACTIVE
                existing.completed_at = None
                existing.save(update_fields=['status', 'completed_at'])
                enrollment = existing
            else:
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

            # Clone datasets that belong to the course; library datasets (course=None)
            # are shared and keep being referenced as-is.
            for ds in course.datasets.all():
                old_id = ds.id
                new_ds = Dataset.objects.create(
                    name=ds.name,
                    description=ds.description,
                    course=new_course,
                    created_by=request.user,
                    database_type=ds.database_type,
                    schema_sql=ds.schema_sql,
                    seed_sql=ds.seed_sql,
                    quick_start_queries=ds.quick_start_queries,
                    is_default=ds.is_default,
                )
                dataset_map[old_id] = new_ds

            def cloned_dataset(dataset_id):
                if dataset_id is None:
                    return None
                return dataset_map.get(dataset_id) or Dataset.objects.filter(pk=dataset_id).first()

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

            # Clone lessons (and their exercises)
            for lesson in course.lessons.all():
                new_lesson = Lesson.objects.create(
                    course=new_course,
                    module=module_map.get(lesson.module_id),
                    title=lesson.title,
                    description=lesson.description,
                    lesson_type=lesson.lesson_type,
                    order=lesson.order,
                    theory_content=lesson.theory_content,
                    time_limit_seconds=lesson.time_limit_seconds,
                    max_attempts=lesson.max_attempts,
                    is_published=lesson.is_published,
                )
                for ex in lesson.exercises.all():
                    LessonExercise.objects.create(
                        lesson=new_lesson,
                        order=ex.order,
                        title=ex.title,
                        description=ex.description,
                        initial_code=ex.initial_code,
                        expected_query=ex.expected_query,
                        expected_result=ex.expected_result,
                        required_keywords=ex.required_keywords,
                        forbidden_keywords=ex.forbidden_keywords,
                        order_matters=ex.order_matters,
                        max_score=ex.max_score,
                        hints=ex.hints,
                        check_datasets=ex.check_datasets,
                        criteria=ex.criteria,
                        ignore_column_order=ex.ignore_column_order,
                        dataset=cloned_dataset(ex.dataset_id),
                    )

            # Clone assignments
            for asn in Assignment.objects.filter(course=course):
                Assignment.objects.create(
                    course=new_course,
                    module=module_map.get(asn.module_id),
                    dataset=cloned_dataset(asn.dataset_id),
                    check_datasets=asn.check_datasets,
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
                    ignore_column_order=asn.ignore_column_order,
                    criteria=asn.criteria,
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


    @action(detail=True, methods=['get'], url_path='timers')
    def timers(self, request, pk=None):
        """A student's clock in every published timed lesson (course owner or admin)."""
        from submissions.timing import course_timers

        course = get_object_or_404(Course, pk=pk)
        require_course_manager(request.user, course)
        student = _course_student(course, request.query_params.get('student'))
        lessons = course.lessons.filter(
            is_published=True, time_limit_seconds__gt=0,
        ).exclude(lesson_type='theory').order_by('order', 'created_at')
        return Response(course_timers(student, lessons))


def _course_student(course, student_id):
    """A user enrolled (in any status) in the course, for the instructor tools."""
    if not student_id:
        raise ValidationError({'student': 'This parameter is required.'})
    enrollment = get_object_or_404(
        Enrollment.objects.select_related('student'), course=course, student_id=student_id,
    )
    return enrollment.student


class DatasetViewSet(viewsets.ModelViewSet):
    serializer_class = DatasetSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None

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
        serializer.save(course_id=course_id, created_by=self.request.user)


class StandaloneDatasetViewSet(viewsets.ModelViewSet):
    """Datasets owned by an instructor (course=None) or system datasets.

    Visible to instructors/admins. Each instructor sees their own datasets
    plus system datasets (created_by=null). Admins see all.
    """
    serializer_class = DatasetSerializer
    permission_classes = [IsAuthenticated, IsInstructor]
    pagination_class = None

    def get_queryset(self):
        user = self.request.user
        # Standalone (course=None) datasets only
        queryset = Dataset.objects.filter(course__isnull=True).select_related('created_by')
        if not user.is_superuser:
            from django.db.models import Q
            queryset = queryset.filter(Q(created_by=user) | Q(created_by__isnull=True))
        return queryset.order_by('-created_at')

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, course=None)

    def perform_update(self, serializer):
        instance = self.get_object()
        user = self.request.user
        if instance.created_by and instance.created_by != user and not user.is_superuser:
            raise PermissionDenied('You can only edit your own datasets')
        serializer.save()

    def perform_destroy(self, instance):
        user = self.request.user
        if instance.created_by and instance.created_by != user and not user.is_superuser:
            raise PermissionDenied('You can only delete your own datasets')
        instance.delete()

    @action(detail=False, methods=['post'])
    def upload_sql(self, request):
        """Parse an uploaded .sql/.txt file into schema_sql + seed_sql."""
        file = request.FILES.get('file')
        if not file:
            return Response({'detail': 'file is required'}, status=status.HTTP_400_BAD_REQUEST)
        if file.size > 5 * 1024 * 1024:
            return Response({'detail': 'File too large (max 5MB)'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            content = file.read().decode('utf-8', errors='replace')
        except Exception as e:
            return Response({'detail': f'Failed to read file: {e}'}, status=status.HTTP_400_BAD_REQUEST)

        # Naive split: CREATE/ALTER/DROP go to schema, INSERT/UPDATE/DELETE go to seed
        schema_lines = []
        seed_lines = []
        for raw in content.split(';'):
            stmt = raw.strip()
            if not stmt:
                continue
            head = stmt.lstrip().upper()
            if head.startswith(('CREATE', 'ALTER', 'DROP')):
                schema_lines.append(stmt + ';')
            elif head.startswith(('INSERT', 'UPDATE', 'DELETE')):
                seed_lines.append(stmt + ';')
            else:
                # Comments or other statements: keep with schema
                schema_lines.append(stmt + ';')
        return Response({
            'schema_sql': '\n'.join(schema_lines),
            'seed_sql': '\n'.join(seed_lines),
        })

    @action(detail=False, methods=['post'])
    def generate(self, request):
        """Generate a dataset (schema + seed) via Gemini AI based on a topic prompt."""
        from .gemini_service import generate_dataset

        topic = (request.data.get('topic') or '').strip()
        size = (request.data.get('size') or 'medium').strip()
        database_type = (request.data.get('database_type') or 'sqlite').strip()

        if not topic:
            return Response({'detail': 'topic is required'}, status=status.HTTP_400_BAD_REQUEST)
        if len(topic) > 500:
            return Response({'detail': 'topic is too long (max 500 chars)'}, status=status.HTTP_400_BAD_REQUEST)

        result = generate_dataset(topic=topic, size=size, database_type=database_type)
        if not result.success:
            not_configured = 'not configured' in (result.error or '').lower()
            return Response(
                {'detail': result.error},
                status=status.HTTP_503_SERVICE_UNAVAILABLE if not_configured
                else status.HTTP_502_BAD_GATEWAY,
            )

        return Response({
            'name': result.name,
            'description': result.description,
            'schema_sql': result.schema_sql,
            'seed_sql': result.seed_sql,
        })

    @action(detail=True, methods=['post'])
    def preview(self, request, pk=None):
        """Run the dataset's schema+seed in the sandbox and return the resulting tables."""
        from sandbox.services import execute_query
        dataset = self.get_object()
        # Pick a sensible default query per database type
        default_queries = {
            'sqlite': "SELECT name FROM sqlite_master WHERE type='table';",
            'postgresql': "SELECT tablename FROM pg_tables WHERE schemaname='public';",
            'mariadb': "SHOW TABLES;",
            'mongodb': "db.getCollectionNames();",
            'redis': "KEYS *",
        }
        query = request.data.get('query') or default_queries.get(dataset.database_type, '')
        if not query:
            return Response({'detail': 'No preview query for this database type'},
                            status=status.HTTP_400_BAD_REQUEST)
        response = execute_query(
            database_type=dataset.database_type,
            query=query,
            schema_sql=dataset.schema_sql,
            seed_sql=dataset.seed_sql,
            timeout=15,
            user_id=request.user.id,
            dataset_id=dataset.id,
        )
        if response.success and response.result:
            return Response(response.result.to_dict())
        return Response({
            'success': False,
            'error_message': response.error_message,
        }, status=status.HTTP_400_BAD_REQUEST)


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

        # Drafts are for the course owner and admins; everyone else sees published lessons.
        owns_course = (
            user.is_authenticated
            and (getattr(user, 'role', None) == 'admin' or user.is_superuser
                 or Course.objects.filter(id=course_id, instructor=user).exists())
        )
        if not owns_course:
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

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        course_id = self.kwargs.get('course_pk')
        if course_id:
            ctx['course'] = Course.objects.filter(id=course_id).first()
        return ctx

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

    @action(detail=True, methods=['post'], url_path='start')
    def start(self, request, course_pk=None, pk=None):
        """Open the practice: records the student's start time and returns the deadline."""
        from submissions.timing import timing_for

        lesson = self.get_object()
        if lesson.lesson_type == 'theory':
            return Response({'detail': 'This lesson has no practice component'},
                            status=status.HTTP_400_BAD_REQUEST)

        user = request.user
        if user.is_instructor:
            # Preview only; nothing is recorded for instructors.
            return Response({
                'started_at': None,
                'time_limit_seconds': lesson.time_limit_seconds,
                'deadline': None,
                'remaining_seconds': lesson.time_limit_seconds,
            })

        if not lesson.is_published:
            return Response({'detail': 'This content is not available'},
                            status=status.HTTP_400_BAD_REQUEST)
        if not lesson.course.enrollments.filter(student=user, status='active').exists():
            return Response({'detail': 'Not enrolled in this course'},
                            status=status.HTTP_403_FORBIDDEN)
        return Response(timing_for(user, lesson))

    @action(detail=True, methods=['post'], url_path='validate-exercises',
            permission_classes=[IsAuthenticated, IsInstructor])
    def validate_exercises(self, request, course_pk=None, pk=None):
        """Report which wrong answers the exercise datasets cannot distinguish from the reference."""
        from grading.compose import QueryShapeError
        from grading.mutants import validate_datasets
        from grading.runner import build_task, make_runner

        lesson = self.get_object()
        if lesson.course.instructor != request.user and not request.user.is_superuser:
            raise PermissionDenied('Not authorized for this lesson')

        db_type = lesson.course.database_type
        timeout = lesson.time_limit_seconds or 600
        report = []
        for exercise in lesson.exercises.select_related('dataset'):
            entry = {'exercise_id': str(exercise.id), 'title': exercise.title}
            if not exercise.expected_query:
                entry['skipped'] = 'no expected_query'
                report.append(entry)
                continue

            task = build_task(
                db_type,
                reference_query=exercise.expected_query,
                dataset=exercise.dataset,
                check_datasets=exercise.check_datasets,
            )
            try:
                result = validate_datasets(
                    exercise.expected_query,
                    [task.primary, *task.hidden],
                    make_runner(db_type, timeout),
                    db_type,
                )
            except QueryShapeError as err:
                entry['error'] = str(err)
                report.append(entry)
                continue

            entry.update({
                'datasets': [task.primary.name, *(d.name for d in task.hidden)],
                'mutants_total': result.mutants_total,
                'checked': result.checked,
                'truncated': result.truncated,
                'killed': result.killed,
                'surviving': [
                    {'kind': m.kind, 'description': m.description, 'sql': m.sql}
                    for m in result.surviving
                ],
                'reference_empty_on': result.reference_empty_on,
                'reference_errors': result.reference_errors,
                'warnings': result.warnings,
            })
            report.append(entry)

        return Response({'lesson_id': str(lesson.id), 'exercises': report})

    def _managed_lesson(self, course_pk, pk):
        """The lesson, for its course owner or an admin; 403 for anyone else."""
        lesson = get_object_or_404(
            Lesson.objects.select_related('course'), pk=pk, course_id=course_pk,
        )
        require_course_manager(self.request.user, lesson.course)
        return lesson

    @action(detail=True, methods=['post'], url_path='timer')
    def timer(self, request, course_pk=None, pk=None):
        """Reset or extend one student's clock in this lesson."""
        from submissions.serializers import TimerActionSerializer
        from submissions.timing import extend_timer, reset_timer

        lesson = self._managed_lesson(course_pk, pk)
        payload = TimerActionSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        if not lesson.time_limit_seconds:
            return Response({'detail': 'This lesson has no time limit'},
                            status=status.HTTP_400_BAD_REQUEST)
        student = _course_student(lesson.course, payload.validated_data['student'])
        if payload.validated_data['action'] == 'reset':
            return Response(reset_timer(student, lesson))
        return Response(extend_timer(student, lesson, payload.validated_data['minutes']))

    @action(detail=True, methods=['post'], url_path='regrade')
    def regrade(self, request, course_pk=None, pk=None):
        """Regrade the stored answers of this lesson, or of one exercise in it."""
        from submissions.regrade import regrade_lesson

        lesson = self._managed_lesson(course_pk, pk)
        exercises = lesson.exercises.select_related('dataset')
        exercise_id = request.data.get('exercise_id')
        if exercise_id:
            exercises = [get_object_or_404(exercises, pk=exercise_id)]
        return Response(regrade_lesson(lesson, exercises))

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
            # Students see modules that are either published themselves
            # or contain at least one published lesson (so they have something to show).
            queryset = queryset.filter(
                Q(is_published=True) | Q(lessons__is_published=True)
            ).distinct()
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
