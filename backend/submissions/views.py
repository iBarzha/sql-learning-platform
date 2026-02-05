from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Sum, Avg, Count

from .models import Submission, UserResult
from .serializers import (
    SubmissionSerializer,
    SubmissionCreateSerializer,
    SubmissionResultSerializer,
    UserResultSerializer,
)
from assignments.models import Assignment
from courses.models import Lesson
from config.permissions import IsSubmissionOwner


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
                assignment = Assignment.objects.get(id=assignment_id)
            except Assignment.DoesNotExist:
                return Response(
                    {'detail': 'Assignment not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            course = assignment.course
            max_attempts = assignment.max_attempts
            is_published = assignment.is_published
        elif lesson_id:
            try:
                lesson = Lesson.objects.get(id=lesson_id)
            except Lesson.DoesNotExist:
                return Response(
                    {'detail': 'Lesson not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            course = lesson.course
            max_attempts = lesson.max_attempts
            is_published = lesson.is_published

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

        submission = Submission.objects.create(
            student=request.user,
            assignment=assignment,
            lesson=lesson,
            query=serializer.validated_data['query'],
            attempt_number=attempt_number
        )

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
            # Get course from assignment or lesson
            course = None
            if result.assignment:
                course = result.assignment.course
            elif result.lesson:
                course = result.lesson.course

            if not course:
                continue

            if course.id not in courses_data:
                # Count published assignments and practice lessons
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

            # Calculate max score
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
