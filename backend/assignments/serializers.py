from rest_framework import serializers
from .models import Assignment
from courses.models import Course
from courses.serializers import (
    DatasetSerializer,
    criteria_summary,
    criteria_task,
    validate_criteria_value,
)

CRITERIA_SOURCE_FIELDS = ('expected_query', 'check_datasets', 'required_keywords',
                          'forbidden_keywords', 'order_matters', 'expected_result')


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

    def _get_user_result(self, obj):
        """Get user result from prefetched data or fall back to query."""
        if hasattr(obj, '_prefetched_user_results'):
            results = obj._prefetched_user_results
            return results[0] if results else None
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.user_results.filter(student=request.user).first()
        return None

    def get_user_best_score(self, obj):
        result = self._get_user_result(obj)
        return float(result.best_score) if result else None

    def get_user_completed(self, obj):
        result = self._get_user_result(obj)
        return result.is_completed if result else False


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
    criteria_summary = serializers.SerializerMethodField()

    class Meta:
        model = Assignment
        fields = [
            'id', 'title', 'description', 'instructions', 'course',
            'course_title', 'database_type', 'dataset', 'query_type', 'difficulty',
            'required_keywords', 'forbidden_keywords', 'order_matters',
            'partial_match', 'max_score', 'time_limit_seconds',
            'max_attempts', 'hints', 'due_date', 'is_published', 'order',
            'submission_count', 'average_score', 'user_attempts',
            'user_best_score', 'user_completed', 'criteria_summary',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'course', 'created_at', 'updated_at']

    def get_criteria_summary(self, obj):
        return criteria_summary(obj.course.database_type, obj)

    def _get_user_result(self, obj):
        """Get user result from prefetched data or fall back to query."""
        if hasattr(obj, '_prefetched_user_results'):
            results = obj._prefetched_user_results
            return results[0] if results else None
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.user_results.filter(student=request.user).first()
        return None

    def get_user_attempts(self, obj):
        result = self._get_user_result(obj)
        return result.total_attempts if result else 0

    def get_user_best_score(self, obj):
        result = self._get_user_result(obj)
        return float(result.best_score) if result else None

    def get_user_completed(self, obj):
        result = self._get_user_result(obj)
        return result.is_completed if result else False


class AssignmentCreateSerializer(serializers.ModelSerializer):
    criteria = serializers.JSONField(required=False, allow_null=True)

    class Meta:
        model = Assignment
        fields = [
            'title', 'description', 'instructions', 'dataset',
            'query_type', 'difficulty', 'expected_query', 'expected_result',
            'check_datasets', 'criteria',
            'required_keywords', 'forbidden_keywords', 'order_matters',
            'partial_match', 'max_score', 'time_limit_seconds',
            'max_attempts', 'hints', 'due_date', 'is_published', 'order'
        ]

    def validate_check_datasets(self, value):
        from courses.serializers import validate_check_datasets_value
        return validate_check_datasets_value(value)

    def _db_type(self):
        if self.instance is not None:
            return self.instance.course.database_type
        view = self.context.get('view')
        course_id = getattr(view, 'kwargs', {}).get('course_pk') if view else None
        course = Course.objects.filter(id=course_id).first() if course_id else None
        return course.database_type if course else 'sqlite'

    def validate(self, attrs):
        # A partial update may omit the reference or datasets: fall back to the stored ones.
        merged = {}
        if self.instance is not None:
            merged = {name: getattr(self.instance, name) for name in CRITERIA_SOURCE_FIELDS}
            merged['criteria'] = self.instance.criteria
        merged.update(attrs)
        if 'criteria' in attrs or self.instance is None:
            attrs['criteria'] = validate_criteria_value(
                criteria_task(self._db_type(), merged), attrs.get('criteria'))
        else:
            # The reference may have changed under a stored choice: keep what still applies.
            from grading.criteria import normalize_config
            attrs['criteria'] = normalize_config(criteria_task(self._db_type(), merged),
                                                 merged.get('criteria'))
        return attrs


class AssignmentInstructorSerializer(AssignmentDetailSerializer):
    """Includes expected query for instructors."""

    class Meta(AssignmentDetailSerializer.Meta):
        fields = AssignmentDetailSerializer.Meta.fields + [
            'expected_query', 'expected_result', 'check_datasets', 'criteria',
        ]
