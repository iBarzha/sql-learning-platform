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
from config.permissions import IsSubmissionOwner


class SubmissionViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'post', 'head', 'options']

    def get_queryset(self):
        user = self.request.user
        assignment_id = self.kwargs.get('assignment_pk')

        if user.is_instructor:
            queryset = Submission.objects.filter(
                assignment__course__instructor=user
            )
        else:
            queryset = Submission.objects.filter(student=user)

        if assignment_id:
            queryset = queryset.filter(assignment_id=assignment_id)

        return queryset.select_related('student', 'assignment')

    def get_serializer_class(self):
        if self.action == 'create':
            return SubmissionCreateSerializer
        if self.action == 'retrieve':
            return SubmissionResultSerializer
        return SubmissionSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        assignment = serializer.validated_data['assignment']

        if not assignment.course.enrollments.filter(
            student=request.user, status='active'
        ).exists():
            return Response(
                {'detail': 'Not enrolled in this course'},
                status=status.HTTP_403_FORBIDDEN
            )

        if not assignment.is_published:
            return Response(
                {'detail': 'Assignment is not available'},
                status=status.HTTP_400_BAD_REQUEST
            )

        user_result, _ = UserResult.objects.get_or_create(
            student=request.user,
            assignment=assignment
        )

        if assignment.max_attempts and user_result.total_attempts >= assignment.max_attempts:
            return Response(
                {'detail': 'Maximum attempts reached'},
                status=status.HTTP_400_BAD_REQUEST
            )

        attempt_number = user_result.total_attempts + 1

        submission = Submission.objects.create(
            student=request.user,
            assignment=assignment,
            query=serializer.validated_data['query'],
            attempt_number=attempt_number
        )

        result_serializer = SubmissionResultSerializer(submission)
        return Response(result_serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'])
    def my_submissions(self, request):
        """Get all submissions for the current user."""
        submissions = Submission.objects.filter(
            student=request.user
        ).select_related('assignment').order_by('-submitted_at')

        serializer = SubmissionSerializer(submissions, many=True)
        return Response(serializer.data)


class UserResultViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = UserResultSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        assignment_id = self.kwargs.get('assignment_pk')
        course_id = self.request.query_params.get('course')

        if user.is_instructor:
            queryset = UserResult.objects.filter(
                assignment__course__instructor=user
            )
        else:
            queryset = UserResult.objects.filter(student=user)

        if assignment_id:
            queryset = queryset.filter(assignment_id=assignment_id)
        if course_id:
            queryset = queryset.filter(assignment__course_id=course_id)

        return queryset.select_related('student', 'assignment', 'best_submission')

    @action(detail=False, methods=['get'])
    def my_progress(self, request):
        """Get current user's progress across all enrolled courses."""
        results = UserResult.objects.filter(
            student=request.user
        ).select_related('assignment__course')

        courses_data = {}
        for result in results:
            course = result.assignment.course
            if course.id not in courses_data:
                total_assignments = course.assignments.filter(is_published=True).count()
                courses_data[course.id] = {
                    'course_id': str(course.id),
                    'course_title': course.title,
                    'total_assignments': total_assignments,
                    'completed_assignments': 0,
                    'total_score': 0,
                    'max_possible_score': 0,
                }

            courses_data[course.id]['max_possible_score'] += result.assignment.max_score
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
