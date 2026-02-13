from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Count, Avg, Max, Min, Prefetch

from .models import Assignment
from submissions.models import UserResult
from .serializers import (
    AssignmentListSerializer,
    AssignmentDetailSerializer,
    AssignmentCreateSerializer,
    AssignmentInstructorSerializer,
)
from courses.models import Course
from config.permissions import IsInstructor, IsCourseInstructor


class AssignmentViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        course_id = self.kwargs.get('course_pk')

        queryset = Assignment.objects.annotate(
            submission_count=Count('submissions', distinct=True),
            average_score=Avg('submissions__score')
        )

        if course_id:
            queryset = queryset.filter(course_id=course_id)

        # Prefetch user results for the current user to avoid N+1 in serializers
        if user.is_authenticated:
            queryset = queryset.prefetch_related(
                Prefetch(
                    'user_results',
                    queryset=UserResult.objects.filter(student=user),
                    to_attr='_prefetched_user_results',
                )
            )

        if user.is_instructor:
            return queryset.filter(course__instructor=user)
        else:
            return queryset.filter(
                course__enrollments__student=user,
                course__enrollments__status='active',
                is_published=True
            )

    def get_serializer_class(self):
        if self.action == 'list':
            return AssignmentListSerializer
        if self.action in ['create', 'update', 'partial_update']:
            return AssignmentCreateSerializer
        if self.request.user.is_instructor:
            return AssignmentInstructorSerializer
        return AssignmentDetailSerializer

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
            raise PermissionDenied('Not authorized to add assignments to this course')
        serializer.save(course=course)

    @action(detail=True, methods=['get'])
    def stats(self, request, pk=None, course_pk=None):
        """Get statistics for an assignment (instructor only)."""
        assignment = self.get_object()

        if assignment.course.instructor != request.user:
            return Response(
                {'detail': 'Not authorized'},
                status=status.HTTP_403_FORBIDDEN
            )

        total_students = assignment.course.enrollments.filter(status='active').count()
        completed_count = assignment.user_results.filter(is_completed=True).count()
        attempted_count = assignment.user_results.count()

        score_stats = assignment.submissions.aggregate(
            total_submissions=Count('id'),
            average_score=Avg('score'),
            highest_score=Max('score'),
            lowest_score=Min('score'),
        )

        return Response({
            'total_students': total_students,
            'attempted_count': attempted_count,
            'completed_count': completed_count,
            'completion_rate': (completed_count / total_students * 100) if total_students > 0 else 0,
            'total_submissions': score_stats['total_submissions'],
            'average_score': score_stats['average_score'],
            'highest_score': score_stats['highest_score'],
            'lowest_score': score_stats['lowest_score'],
        })
