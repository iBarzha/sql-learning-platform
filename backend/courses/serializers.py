from rest_framework import serializers
from .models import Course, Enrollment, Dataset, Lesson, Module
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
    lesson_count = serializers.IntegerField(read_only=True)
    is_enrolled = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = [
            'id', 'title', 'description', 'instructor', 'instructor_name',
            'database_type', 'is_published', 'student_count', 'assignment_count',
            'lesson_count', 'start_date', 'end_date', 'is_enrolled', 'created_at'
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
    lesson_count = serializers.IntegerField(read_only=True)
    is_enrolled = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = [
            'id', 'title', 'description', 'instructor', 'database_type',
            'is_published', 'enrollment_key', 'max_students', 'start_date',
            'end_date', 'student_count', 'assignment_count', 'lesson_count',
            'datasets', 'is_enrolled', 'created_at', 'updated_at'
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


class LessonListSerializer(serializers.ModelSerializer):
    dataset_name = serializers.CharField(source='dataset.name', read_only=True)
    user_completed = serializers.SerializerMethodField()
    user_best_score = serializers.SerializerMethodField()

    class Meta:
        model = Lesson
        fields = [
            'id', 'title', 'description', 'lesson_type', 'order',
            'module', 'is_published', 'max_score', 'dataset_name',
            'user_completed', 'user_best_score', 'created_at'
        ]

    def get_user_completed(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated and obj.lesson_type != 'theory':
            from submissions.models import UserResult
            return UserResult.objects.filter(
                student=request.user,
                lesson=obj,
                is_completed=True
            ).exists()
        return None

    def get_user_best_score(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated and obj.lesson_type != 'theory':
            from submissions.models import UserResult
            result = UserResult.objects.filter(student=request.user, lesson=obj).first()
            return result.best_score if result else None
        return None


class LessonDetailSerializer(serializers.ModelSerializer):
    dataset = DatasetSerializer(read_only=True)
    dataset_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    module_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    course_title = serializers.CharField(source='course.title', read_only=True)
    database_type = serializers.CharField(source='course.database_type', read_only=True)
    user_completed = serializers.SerializerMethodField()

    class Meta:
        model = Lesson
        fields = [
            'id', 'course', 'course_title', 'database_type', 'title', 'description',
            'lesson_type', 'order', 'module', 'module_id',
            'theory_content', 'practice_description', 'practice_initial_code',
            'expected_query', 'expected_result', 'required_keywords', 'forbidden_keywords',
            'order_matters', 'max_score', 'time_limit_seconds', 'max_attempts',
            'hints', 'dataset', 'dataset_id', 'is_published',
            'user_completed', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'course', 'created_at', 'updated_at']

    def get_user_completed(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated and obj.lesson_type != 'theory':
            from submissions.models import UserResult
            return UserResult.objects.filter(
                student=request.user,
                lesson=obj,
                is_completed=True
            ).exists()
        return None

    def update(self, instance, validated_data):
        dataset_id = validated_data.pop('dataset_id', None)
        module_id = validated_data.pop('module_id', None)
        if dataset_id is not None:
            instance.dataset_id = dataset_id
        if module_id is not None:
            instance.module_id = module_id
        return super().update(instance, validated_data)


class LessonCreateSerializer(serializers.ModelSerializer):
    dataset_id = serializers.UUIDField(required=False, allow_null=True)
    module_id = serializers.UUIDField(required=False, allow_null=True)

    class Meta:
        model = Lesson
        fields = [
            'title', 'description', 'lesson_type', 'order',
            'theory_content', 'practice_description', 'practice_initial_code',
            'expected_query', 'expected_result', 'required_keywords', 'forbidden_keywords',
            'order_matters', 'max_score', 'time_limit_seconds', 'max_attempts',
            'hints', 'dataset_id', 'module_id', 'is_published'
        ]

    def create(self, validated_data):
        dataset_id = validated_data.pop('dataset_id', None)
        module_id = validated_data.pop('module_id', None)
        lesson = Lesson.objects.create(**validated_data)
        changed = False
        if dataset_id:
            lesson.dataset_id = dataset_id
            changed = True
        if module_id:
            lesson.module_id = module_id
            changed = True
        if changed:
            lesson.save()
        return lesson


class ModuleListSerializer(serializers.ModelSerializer):
    lesson_count = serializers.SerializerMethodField()

    class Meta:
        model = Module
        fields = [
            'id', 'title', 'description', 'order',
            'lesson_count', 'is_published', 'created_at',
        ]

    def get_lesson_count(self, obj):
        return obj.lessons.count()


class ModuleDetailSerializer(serializers.ModelSerializer):
    lesson_count = serializers.SerializerMethodField()

    class Meta:
        model = Module
        fields = [
            'id', 'title', 'description', 'order', 'is_published',
            'lesson_count', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_lesson_count(self, obj):
        return obj.lessons.count()


class ModuleCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Module
        fields = ['title', 'description', 'order', 'is_published']
