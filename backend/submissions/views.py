"""Views for submission handling with sandbox execution and grading."""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone

from .models import Submission, UserResult
from .serializers import (
    SubmissionSerializer,
    SubmissionCreateSerializer,
    SubmissionResultSerializer,
    UserResultSerializer,
)
from assignments.models import Assignment
from courses.models import Lesson
from sandbox.services import execute_query
from grading.models import get_grading_service


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

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        assignment_id = self.kwargs.get('assignment_pk')
        lesson_id = self.kwargs.get('lesson_pk')

        assignment = None
        lesson = None
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
            partial_match = getattr(assignment, 'partial_match', False)
            max_score = assignment.max_score
            time_limit = assignment.time_limit_seconds or 30

        elif lesson_id:
            try:
                lesson = Lesson.objects.select_related(
                    'course', 'dataset'
                ).get(id=lesson_id)
            except Lesson.DoesNotExist:
                return Response(
                    {'detail': 'Lesson not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            course = lesson.course
            max_attempts = lesson.max_attempts
            is_published = lesson.is_published
            dataset = lesson.dataset
            expected_query = lesson.expected_query
            expected_result = lesson.expected_result
            required_keywords = lesson.required_keywords or []
            forbidden_keywords = lesson.forbidden_keywords or []
            order_matters = lesson.order_matters
            partial_match = False
            max_score = lesson.max_score
            time_limit = lesson.time_limit_seconds or 60

            if lesson.lesson_type == 'theory':
                return Response(
                    {'detail': 'This lesson has no practice component'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            return Response(
                {'detail': 'Assignment or lesson ID required'},
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

        # Get or create user result
        if assignment:
            user_result, _ = UserResult.objects.get_or_create(
                student=request.user,
                assignment=assignment
            )
        else:
            user_result, _ = UserResult.objects.get_or_create(
                student=request.user,
                lesson=lesson
            )

        if max_attempts and user_result.total_attempts >= max_attempts:
            return Response(
                {'detail': 'Maximum attempts reached'},
                status=status.HTTP_400_BAD_REQUEST
            )

        attempt_number = user_result.total_attempts + 1
        student_query = serializer.validated_data['query']

        # Create submission with pending status
        submission = Submission.objects.create(
            student=request.user,
            assignment=assignment,
            lesson=lesson,
            query=student_query,
            attempt_number=attempt_number,
            status=Submission.Status.RUNNING,
        )

        # Execute query in sandbox
        schema_sql = dataset.schema_sql if dataset else ''
        seed_sql = dataset.seed_sql if dataset else ''

        execution_response = execute_query(
            database_type=course.database_type,
            query=student_query,
            schema_sql=schema_sql,
            seed_sql=seed_sql,
            timeout=time_limit,
            user_id=request.user.id,
            submission_id=submission.id,
            dataset_id=dataset.id if dataset else None,
        )

        # Update submission with execution result
        submission.execution_time_ms = execution_response.execution_time_ms

        if execution_response.success and execution_response.result:
            submission.status = Submission.Status.COMPLETED
            submission.result = execution_response.result.to_dict()
        else:
            submission.status = Submission.Status.ERROR
            submission.error_message = execution_response.error_message
            submission.result = {'success': False, 'error_message': execution_response.error_message}

        # Grade the submission
        grading_service = get_grading_service()

        # Execute expected query to get expected result if not stored
        if expected_query and not expected_result:
            expected_response = execute_query(
                database_type=course.database_type,
                query=expected_query,
                schema_sql=schema_sql,
                seed_sql=seed_sql,
                timeout=time_limit,
            )
            if expected_response.success and expected_response.result:
                expected_result = expected_response.result.to_dict()

        grading_result = grading_service.grade(
            student_result=submission.result or {},
            expected_result=expected_result,
            expected_query=expected_query,
            required_keywords=required_keywords,
            forbidden_keywords=forbidden_keywords,
            order_matters=order_matters,
            partial_match=partial_match,
            max_score=max_score,
            student_query=student_query,
        )

        submission.score = grading_result.score
        submission.is_correct = grading_result.is_correct
        submission.feedback = grading_result.feedback
        submission.graded_at = timezone.now()
        submission.save()

        # Update user result
        user_result.update_from_submission(submission)

        result_serializer = SubmissionResultSerializer(submission)
        return Response(result_serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'])
    def my_submissions(self, request):
        """Get all submissions for the current user."""
        assignment_id = self.kwargs.get('assignment_pk')
        lesson_id = self.kwargs.get('lesson_pk')

        submissions = Submission.objects.filter(student=request.user)

        if assignment_id:
            submissions = submissions.filter(assignment_id=assignment_id)
        if lesson_id:
            submissions = submissions.filter(lesson_id=lesson_id)

        submissions = submissions.select_related(
            'assignment', 'lesson'
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
    def my_progress(self, request):
        """Get current user's progress across all enrolled courses."""
        results = UserResult.objects.filter(
            student=request.user
        ).select_related('assignment__course', 'lesson__course')

        courses_data = {}
        for result in results:
            course = None
            if result.assignment:
                course = result.assignment.course
            elif result.lesson:
                course = result.lesson.course

            if not course:
                continue

            if course.id not in courses_data:
                total_assignments = course.assignments.filter(is_published=True).count()
                total_practice_lessons = course.lessons.filter(
                    is_published=True,
                    lesson_type__in=['practice', 'mixed']
                ).count()

                courses_data[course.id] = {
                    'course_id': str(course.id),
                    'course_title': course.title,
                    'total_assignments': total_assignments + total_practice_lessons,
                    'completed_assignments': 0,
                    'total_score': 0,
                    'max_possible_score': 0,
                }

            if result.assignment:
                max_score = result.assignment.max_score
            elif result.lesson:
                max_score = result.lesson.max_score
            else:
                max_score = 0

            courses_data[course.id]['max_possible_score'] += max_score
            if result.is_completed:
                courses_data[course.id]['completed_assignments'] += 1
            courses_data[course.id]['total_score'] += float(result.best_score)

        for data in courses_data.values():
            if data['total_assignments'] > 0:
                data['completion_rate'] = round(
                    data['completed_assignments'] / data['total_assignments'] * 100, 2
                )
            else:
                data['completion_rate'] = 0

            if data['max_possible_score'] > 0:
                data['percentage_score'] = round(
                    data['total_score'] / data['max_possible_score'] * 100, 2
                )
            else:
                data['percentage_score'] = 0

        return Response(list(courses_data.values()))
