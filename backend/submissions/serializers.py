from rest_framework import serializers
from .models import Submission, UserResult
from users.serializers import UserSerializer


class SubmissionSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.full_name', read_only=True)
    assignment_title = serializers.CharField(source='assignment.title', read_only=True)

    class Meta:
        model = Submission
        fields = [
            'id', 'student', 'student_name', 'assignment', 'assignment_title',
            'query', 'status', 'result', 'error_message', 'execution_time_ms',
            'score', 'is_correct', 'feedback', 'attempt_number',
            'submitted_at', 'graded_at'
        ]
        read_only_fields = [
            'id', 'student', 'status', 'result', 'error_message',
            'execution_time_ms', 'score', 'is_correct', 'feedback',
            'attempt_number', 'submitted_at', 'graded_at'
        ]


class SubmissionCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Submission
        fields = ['query']


class SubmissionResultSerializer(serializers.ModelSerializer):
    """Detailed submission result after grading."""

    class Meta:
        model = Submission
        fields = [
            'id', 'query', 'status', 'result', 'error_message',
            'execution_time_ms', 'score', 'is_correct', 'feedback',
            'attempt_number', 'submitted_at', 'graded_at'
        ]


class UserResultSerializer(serializers.ModelSerializer):
    student = UserSerializer(read_only=True)
    assignment_title = serializers.CharField(source='assignment.title', read_only=True)
    best_submission = SubmissionSerializer(read_only=True)

    class Meta:
        model = UserResult
        fields = [
            'id', 'student', 'assignment', 'assignment_title',
            'best_submission', 'best_score', 'total_attempts',
            'is_completed', 'first_completed_at', 'last_attempt_at'
        ]


class StudentProgressSerializer(serializers.Serializer):
    """Summary of student progress in a course."""
    student = UserSerializer(read_only=True)
    total_assignments = serializers.IntegerField()
    completed_assignments = serializers.IntegerField()
    total_score = serializers.DecimalField(max_digits=8, decimal_places=2)
    average_score = serializers.DecimalField(max_digits=5, decimal_places=2)
    completion_rate = serializers.DecimalField(max_digits=5, decimal_places=2)
