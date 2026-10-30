from django.utils import timezone
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
            'lesson', 'exercise',
            'query', 'status', 'result', 'error_message', 'execution_time_ms',
            'score', 'is_correct', 'feedback', 'attempt_number',
            'submitted_at', 'graded_at'
        ]
        read_only_fields = [
            'id', 'student', 'status', 'result', 'error_message',
            'execution_time_ms', 'score', 'is_correct', 'feedback',
            'attempt_number', 'submitted_at', 'graded_at'
        ]


class SubmissionCreateSerializer(serializers.Serializer):
    query = serializers.CharField(max_length=50000)
    exercise_id = serializers.UUIDField(required=False)


class SubmissionResultSerializer(serializers.ModelSerializer):
    """Detailed submission result after grading."""

    class Meta:
        model = Submission
        fields = [
            'id', 'lesson', 'exercise', 'assignment',
            'query', 'status', 'result', 'error_message',
            'execution_time_ms', 'score', 'is_correct', 'feedback',
            'attempt_number', 'submitted_at', 'graded_at'
        ]


class UserResultSerializer(serializers.ModelSerializer):
    student = UserSerializer(read_only=True)
    assignment_title = serializers.CharField(source='assignment.title', read_only=True)
    lesson_title = serializers.CharField(source='lesson.title', read_only=True)
    exercise_title = serializers.CharField(source='exercise.title', read_only=True)
    best_submission = SubmissionSerializer(read_only=True)
    max_score = serializers.IntegerField(read_only=True, allow_null=True)
    effective_score = serializers.DecimalField(max_digits=5, decimal_places=2, read_only=True)

    class Meta:
        model = UserResult
        fields = [
            'id', 'student', 'assignment', 'assignment_title',
            'lesson', 'lesson_title', 'exercise', 'exercise_title',
            'best_submission', 'best_score', 'total_attempts',
            'is_completed', 'first_completed_at', 'last_attempt_at',
            'max_score', 'extra_seconds',
            'manual_score', 'manual_comment', 'manual_set_at', 'effective_score',
        ]
        read_only_fields = fields


class ManualScoreSerializer(serializers.ModelSerializer):
    """The instructor's override of a result's score; null removes it."""

    class Meta:
        model = UserResult
        fields = ['manual_score', 'manual_comment']

    def validate(self, attrs):
        max_score = self.instance.max_score
        if max_score is None:
            raise serializers.ValidationError('This result has no task to score.')
        score = attrs.get('manual_score')
        if score is not None and not 0 <= score <= max_score:
            raise serializers.ValidationError(
                {'manual_score': f'Must be between 0 and {max_score}.'})
        return attrs

    def update(self, instance, validated_data):
        for field, value in validated_data.items():
            setattr(instance, field, value)
        if instance.manual_score is None and not instance.manual_comment:
            instance.manual_set_by = None
            instance.manual_set_at = None
        else:
            instance.manual_set_by = self.context['request'].user
            instance.manual_set_at = timezone.now()
        instance.save(update_fields=['manual_score', 'manual_comment',
                                     'manual_set_by', 'manual_set_at'])
        return instance


class TimerActionSerializer(serializers.Serializer):
    """Instructor's change to one student's lesson clock."""
    student = serializers.UUIDField()
    action = serializers.ChoiceField(choices=['reset', 'extend'])
    minutes = serializers.IntegerField(min_value=1, max_value=180, required=False)

    def validate(self, attrs):
        if attrs['action'] == 'extend' and 'minutes' not in attrs:
            raise serializers.ValidationError({'minutes': 'Required for extend.'})
        return attrs


class StudentProgressSerializer(serializers.Serializer):
    """Summary of student progress in a course."""
    student = UserSerializer(read_only=True)
    total_assignments = serializers.IntegerField()
    completed_assignments = serializers.IntegerField()
    total_score = serializers.DecimalField(max_digits=8, decimal_places=2)
    average_score = serializers.DecimalField(max_digits=5, decimal_places=2)
    completion_rate = serializers.DecimalField(max_digits=5, decimal_places=2)
