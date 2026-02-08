from rest_framework import serializers
from .models import Assignment
from courses.serializers import DatasetSerializer


class AssignmentListSerializer(serializers.ModelSerializer):
    course_title = serializers.CharField(source='course.title', read_only=True)
    dataset_name = serializers.CharField(source='dataset.name', read_only=True)
    submission_count = serializers.IntegerField(read_only=True)
    user_best_score = serializers.SerializerMethodField()
    user_completed = serializers.SerializerMethodField()

    class Meta:
        model = Assignment
        fields = [
            'id', 'title', 'description', 'course', 'course_title',
            'dataset', 'dataset_name', 'query_type', 'difficulty',
            'max_score', 'due_date', 'is_published', 'order',
            'submission_count', 'user_best_score', 'user_completed'
        ]
        read_only_fields = ['id', 'course']

    def get_user_best_score(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            result = obj.user_results.filter(student=request.user).first()
            return float(result.best_score) if result else None
        return None

    def get_user_completed(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            result = obj.user_results.filter(student=request.user).first()
            return result.is_completed if result else False
        return False


class AssignmentDetailSerializer(serializers.ModelSerializer):
    course_title = serializers.CharField(source='course.title', read_only=True)
    database_type = serializers.CharField(source='course.database_type', read_only=True)
    dataset = DatasetSerializer(read_only=True)
    submission_count = serializers.IntegerField(read_only=True)
    average_score = serializers.DecimalField(
        max_digits=5, decimal_places=2, read_only=True
    )
    user_attempts = serializers.SerializerMethodField()
    user_best_score = serializers.SerializerMethodField()
    user_completed = serializers.SerializerMethodField()

    class Meta:
        model = Assignment
        fields = [
            'id', 'title', 'description', 'instructions', 'course',
            'course_title', 'database_type', 'dataset', 'query_type', 'difficulty',
            'required_keywords', 'forbidden_keywords', 'order_matters',
            'partial_match', 'max_score', 'time_limit_seconds',
            'max_attempts', 'hints', 'due_date', 'is_published', 'order',
            'submission_count', 'average_score', 'user_attempts',
            'user_best_score', 'user_completed', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'course', 'created_at', 'updated_at']

    def get_user_attempts(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            result = obj.user_results.filter(student=request.user).first()
            return result.total_attempts if result else 0
        return 0

    def get_user_best_score(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            result = obj.user_results.filter(student=request.user).first()
            return float(result.best_score) if result else None
        return None

    def get_user_completed(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            result = obj.user_results.filter(student=request.user).first()
            return result.is_completed if result else False
        return False


class AssignmentCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Assignment
        fields = [
            'title', 'description', 'instructions', 'dataset',
            'query_type', 'difficulty', 'expected_query', 'expected_result',
            'required_keywords', 'forbidden_keywords', 'order_matters',
            'partial_match', 'max_score', 'time_limit_seconds',
            'max_attempts', 'hints', 'due_date', 'is_published', 'order'
        ]


class AssignmentInstructorSerializer(AssignmentDetailSerializer):
    """Includes expected query for instructors."""

    class Meta(AssignmentDetailSerializer.Meta):
        fields = AssignmentDetailSerializer.Meta.fields + ['expected_query', 'expected_result']
