"""Views for submission handling with sandbox execution and grading."""

import uuid

from django.db import transaction
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit

from .models import Submission, UserResult
from .progress import course_progress
from .storage import json_safe
from .serializers import (
    SubmissionSerializer,
    SubmissionCreateSerializer,
    SubmissionResultSerializer,
    UserResultSerializer,
)
from assignments.models import Assignment
from courses.models import Course, Enrollment, Lesson, LessonExercise
from grading.runner import build_task, make_runner, make_sequence_runner
from grading.service import grade as grade_submission


class SubmissionViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'post', 'head', 'options']

    def get_queryset(self):
        user = self.request.user
        assignment_id = self.kwargs.get('assignment_pk')
        lesson_id = self.kwargs.get('lesson_pk')

        if user.is_instructor:
            queryset = Submission.objects.filter(
                assignment__course__instructor=user
            ) | Submission.objects.filter(
                lesson__course__instructor=user
            )
        else:
            queryset = Submission.objects.filter(student=user)

        if assignment_id:
            queryset = queryset.filter(assignment_id=assignment_id)
        if lesson_id:
            queryset = queryset.filter(lesson_id=lesson_id)

        return queryset.select_related('student', 'assignment', 'lesson')

    def get_serializer_class(self):
        if self.action == 'create':
            return SubmissionCreateSerializer
        if self.action == 'retrieve':
            return SubmissionResultSerializer
        return SubmissionSerializer

    @method_decorator(ratelimit(key='user', rate='10/m', method='POST'))
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        assignment_id = self.kwargs.get('assignment_pk')
        lesson_id = self.kwargs.get('lesson_pk')

        assignment = None
        lesson = None
        exercise = None
        course = None

        if assignment_id:
            try:
                assignment = Assignment.objects.select_related(
                    'course', 'dataset'
                ).get(id=assignment_id)
            except Assignment.DoesNotExist:
                return Response(
                    {'detail': 'Assignment not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            course = assignment.course
            max_attempts = assignment.max_attempts
            is_published = assignment.is_published
            dataset = assignment.dataset
            expected_query = assignment.expected_query
            expected_result = assignment.expected_result
            required_keywords = assignment.required_keywords or []
            forbidden_keywords = assignment.forbidden_keywords or []
            order_matters = assignment.order_matters
            max_score = assignment.max_score
            time_limit = assignment.time_limit_seconds or 30
            check_datasets = assignment.check_datasets or []
            query_type = assignment.query_type
            criteria = assignment.criteria or {}
            ignore_column_order = assignment.ignore_column_order

        elif lesson_id:
            try:
                lesson = Lesson.objects.select_related('course').get(id=lesson_id)
            except Lesson.DoesNotExist:
                return Response(
                    {'detail': 'Lesson not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            if lesson.lesson_type == 'theory':
                return Response(
                    {'detail': 'This lesson has no practice component'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            exercise_id = serializer.validated_data.get('exercise_id')
            if not exercise_id:
                return Response(
                    {'detail': 'exercise_id is required for lesson submissions'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            try:
                exercise = LessonExercise.objects.select_related('dataset').get(
                    id=exercise_id, lesson=lesson
                )
            except LessonExercise.DoesNotExist:
                return Response(
                    {'detail': 'Exercise not found in this lesson'},
                    status=status.HTTP_404_NOT_FOUND
                )
            course = lesson.course
            max_attempts = lesson.max_attempts
            is_published = lesson.is_published
            dataset = exercise.dataset
            expected_query = exercise.expected_query
            expected_result = exercise.expected_result
            required_keywords = exercise.required_keywords or []
            forbidden_keywords = exercise.forbidden_keywords or []
            order_matters = exercise.order_matters
            max_score = exercise.max_score
            time_limit = lesson.time_limit_seconds or 600
            check_datasets = exercise.check_datasets or []
            query_type = 'select'
            criteria = exercise.criteria or {}
            ignore_column_order = exercise.ignore_column_order
        else:
            return Response(
                {'detail': 'Assignment or lesson ID required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate nested URL consistency (lesson/assignment belongs to this course)
        course_pk = self.kwargs.get('course_pk')
        if course_pk and str(course.id) != str(course_pk):
            return Response(
                {'detail': 'Resource does not belong to this course'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check enrollment
        if not course.enrollments.filter(
            student=request.user, status='active'
        ).exists():
            return Response(
                {'detail': 'Not enrolled in this course'},
                status=status.HTTP_403_FORBIDDEN
            )

        if not is_published:
            return Response(
                {'detail': 'This content is not available'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if lesson is not None and lesson.time_limit_seconds:
            from .timing import time_is_up
            if time_is_up(request.user, lesson):
                return Response(
                    {'detail': 'Time is up for this lesson', 'code': 'time_up'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        # Get or create user result (atomic with row locking to prevent race conditions)
        with transaction.atomic():
            if assignment:
                user_result, _ = UserResult.objects.select_for_update().get_or_create(
                    student=request.user,
                    assignment=assignment
                )
            else:
                user_result, _ = UserResult.objects.select_for_update().get_or_create(
                    student=request.user,
                    exercise=exercise,
                    defaults={'lesson': lesson},
                )

            if max_attempts and user_result.total_attempts >= max_attempts:
                return Response(
                    {'detail': 'Maximum attempts reached'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            attempt_number = user_result.total_attempts + 1

        student_query = serializer.validated_data['query']

        # Create submission with running status
        submission = Submission.objects.create(
            student=request.user,
            assignment=assignment,
            lesson=lesson,
            exercise=exercise if lesson else None,
            query=student_query,
            attempt_number=attempt_number,
            status=Submission.Status.RUNNING,
        )

        try:
            task = build_task(
                course.database_type,
                reference_query=expected_query,
                dataset=dataset,
                check_datasets=check_datasets,
                required_keywords=required_keywords,
                forbidden_keywords=forbidden_keywords,
                order_matters=order_matters,
                max_score=max_score,
                query_type=query_type,
                expected_result=expected_result,
                criteria=criteria,
                ignore_column_order=ignore_column_order,
            )
            runner = make_runner(
                course.database_type,
                time_limit,
                user_id=request.user.id,
                submission_id=submission.id,
                dataset_id=dataset.id if dataset else None,
            )
            graded = grade_submission(
                task, student_query, runner,
                run_sequence=make_sequence_runner(course.database_type, time_limit),
                # A timed lesson is a test: the reference rows would hand out the answer.
                reveal_rows=not (lesson is not None and bool(lesson.time_limit_seconds)),
            )
            execution = graded.execution

            submission.execution_time_ms = execution.execution_time_ms
            if execution.success:
                submission.status = Submission.Status.COMPLETED
                submission.result = {
                    'success': True,
                    'columns': json_safe(execution.columns),
                    'rows': json_safe(execution.rows),
                    'row_count': len(execution.rows),
                    'affected_rows': execution.affected_rows,
                    'execution_time_ms': execution.execution_time_ms,
                    'error_message': '',
                    'truncated': execution.truncated,
                }
            else:
                submission.status = Submission.Status.ERROR
                submission.error_message = execution.error
                submission.result = {'success': False, 'error_message': execution.error}

            submission.score = graded.score
            submission.is_correct = graded.passed
            submission.feedback = json_safe(graded.feedback)
            submission.graded_at = timezone.now()
            submission.save()
        except Exception as e:
            submission.status = Submission.Status.ERROR
            submission.error_message = f'Grading failed: {e}'
            submission.save()
            user_result.update_from_submission(submission)
            return Response(
                SubmissionResultSerializer(submission).data,
                status=status.HTTP_201_CREATED
            )

        # Update user result
        user_result.update_from_submission(submission)

        result_serializer = SubmissionResultSerializer(submission)
        return Response(result_serializer.data, status=status.HTTP_201_CREATED)

    # The frontend has always called .../submissions/my/; the default url_path
    # (my_submissions/) never matched it, so the history was silently 404.
    @action(detail=False, methods=['get'], url_path='my')
    def my_submissions(self, request, **kwargs):
        """Get all submissions for the current user."""
        assignment_id = self.kwargs.get('assignment_pk')
        lesson_id = self.kwargs.get('lesson_pk')

        submissions = Submission.objects.filter(student=request.user)

        if assignment_id:
            submissions = submissions.filter(assignment_id=assignment_id)
        if lesson_id:
            submissions = submissions.filter(lesson_id=lesson_id)

        submissions = submissions.select_related(
            'student', 'assignment', 'lesson'
        ).order_by('-submitted_at')

        serializer = SubmissionSerializer(submissions, many=True)
        return Response(serializer.data)


class UserResultViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = UserResultSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        assignment_id = self.kwargs.get('assignment_pk')
        lesson_id = self.kwargs.get('lesson_pk')
        course_id = self.request.query_params.get('course')

        if user.is_instructor:
            queryset = UserResult.objects.filter(
                assignment__course__instructor=user
            ) | UserResult.objects.filter(
                lesson__course__instructor=user
            )
        else:
            queryset = UserResult.objects.filter(student=user)

        if assignment_id:
            queryset = queryset.filter(assignment_id=assignment_id)
        if lesson_id:
            queryset = queryset.filter(lesson_id=lesson_id)
        if course_id:
            queryset = queryset.filter(
                assignment__course_id=course_id
            ) | queryset.filter(
                lesson__course_id=course_id
            )

        return queryset.select_related('student', 'assignment', 'lesson', 'best_submission')

    @action(detail=False, methods=['get'])
    def my_progress(self, request, **kwargs):
        """Current user's progress in every course they are actively enrolled in."""
        courses = Course.objects.filter(
            enrollments__student=request.user, enrollments__status='active',
        ).distinct()
        course_id = request.query_params.get('course')
        if course_id:
            try:
                courses = courses.filter(id=uuid.UUID(str(course_id)))
            except ValueError:
                return Response({'detail': 'Invalid course id.'},
                                status=status.HTTP_400_BAD_REQUEST)
        return Response(course_progress(request.user, courses))

    @action(detail=False, methods=['get'])
    def student_progress(self, request, **kwargs):
        """Get a specific student's progress (instructor only)."""
        if not request.user.is_instructor:
            return Response(
                {'detail': 'Only instructors can view student progress.'},
                status=status.HTTP_403_FORBIDDEN
            )

        student_id = request.query_params.get('student')
        if not student_id:
            return Response(
                {'detail': 'student parameter is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            student = User.objects.get(id=student_id)
        except User.DoesNotExist:
            return Response(
                {'detail': 'Student not found.'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Only the courses this instructor owns.
        courses = Course.objects.filter(
            instructor=request.user,
            enrollments__student=student, enrollments__status='active',
        ).distinct()
        return Response(course_progress(student, courses))
