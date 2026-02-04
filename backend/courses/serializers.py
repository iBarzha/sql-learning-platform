from rest_framework import serializers
from .models import Course, Enrollment, Dataset
from users.serializers import UserSerializer


class DatasetSerializer(serializers.ModelSerializer):
    class Meta:
        model = Dataset
        fields = [
            'id', 'name', 'description', 'schema_sql', 'seed_sql',
            'is_default', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class CourseListSerializer(serializers.ModelSerializer):
    instructor_name = serializers.CharField(source='instructor.full_name', read_only=True)
    student_count = serializers.IntegerField(read_only=True)
    assignment_count = serializers.IntegerField(read_only=True)
    is_enrolled = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = [
            'id', 'title', 'description', 'instructor', 'instructor_name',
            'database_type', 'is_published', 'student_count', 'assignment_count',
            'start_date', 'end_date', 'is_enrolled', 'created_at'
        ]
        read_only_fields = ['id', 'instructor', 'created_at']

    def get_is_enrolled(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.enrollments.filter(student=request.user, status='active').exists()
        return False


class CourseDetailSerializer(serializers.ModelSerializer):
    instructor = UserSerializer(read_only=True)
    datasets = DatasetSerializer(many=True, read_only=True)
    student_count = serializers.IntegerField(read_only=True)
    assignment_count = serializers.IntegerField(read_only=True)
    is_enrolled = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = [
            'id', 'title', 'description', 'instructor', 'database_type',
            'is_published', 'enrollment_key', 'max_students', 'start_date',
            'end_date', 'student_count', 'assignment_count', 'datasets',
            'is_enrolled', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'instructor', 'created_at', 'updated_at']

    def get_is_enrolled(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.enrollments.filter(student=request.user, status='active').exists()
        return False


class CourseCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Course
        fields = [
            'title', 'description', 'database_type', 'is_published',
            'enrollment_key', 'max_students', 'start_date', 'end_date'
        ]

    def create(self, validated_data):
        validated_data['instructor'] = self.context['request'].user
        return super().create(validated_data)


class EnrollmentSerializer(serializers.ModelSerializer):
    student = UserSerializer(read_only=True)
    course_title = serializers.CharField(source='course.title', read_only=True)

    class Meta:
        model = Enrollment
        fields = [
            'id', 'student', 'course', 'course_title', 'status',
            'grade', 'enrolled_at', 'completed_at'
        ]
        read_only_fields = ['id', 'student', 'enrolled_at', 'completed_at']


class EnrollRequestSerializer(serializers.Serializer):
    enrollment_key = serializers.CharField(required=False, allow_blank=True)
