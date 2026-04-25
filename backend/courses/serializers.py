from rest_framework import serializers
from django.db.models import Exists, OuterRef
from .models import Course, Enrollment, Dataset, Lesson, LessonExercise, Module, Attachment
from users.serializers import UserSerializer


class DatasetSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='created_by.full_name', read_only=True, default=None)
    created_by = serializers.UUIDField(source='created_by_id', read_only=True)

    class Meta:
        model = Dataset
        fields = [
            'id', 'name', 'description', 'database_type', 'schema_sql', 'seed_sql',
            'quick_start_queries', 'is_default', 'created_by', 'created_by_name',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_by', 'created_by_name', 'created_at', 'updated_at']


class CourseListSerializer(serializers.ModelSerializer):
    instructor_name = serializers.CharField(source='instructor.full_name', read_only=True)
    student_count = serializers.IntegerField(read_only=True)
    assignment_count = serializers.IntegerField(read_only=True)
    lesson_count = serializers.IntegerField(read_only=True)
    is_enrolled = serializers.BooleanField(read_only=True)
    course_code = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = [
            'id', 'title', 'description', 'instructor', 'instructor_name',
            'database_type', 'is_published', 'student_count', 'assignment_count',
            'lesson_count', 'start_date', 'end_date', 'is_enrolled', 'course_code',
            'created_at'
        ]
        read_only_fields = ['id', 'instructor', 'created_at']

    def get_course_code(self, obj):
        request = self.context.get('request')
        if request and request.user == obj.instructor:
            return obj.course_code
        return None


class CourseDetailSerializer(serializers.ModelSerializer):
    instructor = UserSerializer(read_only=True)
    datasets = DatasetSerializer(many=True, read_only=True)
    student_count = serializers.IntegerField(read_only=True)
    assignment_count = serializers.IntegerField(read_only=True)
    lesson_count = serializers.IntegerField(read_only=True)
    is_enrolled = serializers.BooleanField(read_only=True)
    course_code = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = [
            'id', 'title', 'description', 'instructor', 'database_type',
            'is_published', 'course_code', 'max_students', 'start_date',
            'end_date', 'student_count', 'assignment_count', 'lesson_count',
            'datasets', 'is_enrolled', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'instructor', 'created_at', 'updated_at']

    def get_course_code(self, obj):
        request = self.context.get('request')
        if request and request.user == obj.instructor:
            return obj.course_code
        return None


class CourseCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Course
        fields = [
            'id', 'title', 'description', 'database_type', 'is_published',
            'max_students', 'start_date', 'end_date'
        ]
        read_only_fields = ['id']

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


class JoinByCodeSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=8)


class LessonExerciseSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(required=False)
    dataset = DatasetSerializer(read_only=True)
    dataset_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)

    class Meta:
        model = LessonExercise
        fields = [
            'id', 'order', 'title', 'description', 'initial_code',
            'expected_query', 'expected_result',
            'required_keywords', 'forbidden_keywords', 'order_matters',
            'max_score', 'hints', 'dataset', 'dataset_id',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']


class LessonListSerializer(serializers.ModelSerializer):
    user_completed = serializers.SerializerMethodField()
    user_best_score = serializers.SerializerMethodField()
    exercise_count = serializers.IntegerField(source='exercises.count', read_only=True)

    class Meta:
        model = Lesson
        fields = [
            'id', 'title', 'description', 'lesson_type', 'order',
            'module', 'is_published', 'exercise_count',
            'user_completed', 'user_best_score', 'created_at'
        ]

    def _get_user_results(self, obj):
        if hasattr(obj, '_prefetched_user_results'):
            return obj._prefetched_user_results
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            from submissions.models import UserResult
            return list(UserResult.objects.filter(student=request.user, lesson=obj))
        return []

    def get_user_completed(self, obj):
        if obj.lesson_type == 'theory':
            return None
        results = self._get_user_results(obj)
        if not results:
            return False
        # Lesson is complete only if every exercise has a completed result.
        exercise_ids = {ex.id for ex in obj.exercises.all()}
        if not exercise_ids:
            return False
        completed = {r.exercise_id for r in results if r.is_completed and r.exercise_id}
        return exercise_ids.issubset(completed)

    def get_user_best_score(self, obj):
        if obj.lesson_type == 'theory':
            return None
        results = self._get_user_results(obj)
        if not results:
            return None
        return sum((r.best_score for r in results if r.exercise_id), start=0)


class LessonDetailSerializer(serializers.ModelSerializer):
    module_id = serializers.UUIDField(write_only=True, required=False)
    course_title = serializers.CharField(source='course.title', read_only=True)
    database_type = serializers.CharField(source='course.database_type', read_only=True)
    exercises = LessonExerciseSerializer(many=True, required=False)
    user_completed = serializers.SerializerMethodField()

    class Meta:
        model = Lesson
        fields = [
            'id', 'course', 'course_title', 'database_type', 'title', 'description',
            'lesson_type', 'order', 'module', 'module_id',
            'theory_content', 'time_limit_seconds', 'max_attempts',
            'exercises', 'is_published',
            'user_completed', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'course', 'created_at', 'updated_at']

    def get_user_completed(self, obj):
        if obj.lesson_type == 'theory':
            return None
        request = self.context.get('request')
        if not (request and request.user.is_authenticated):
            return None
        from submissions.models import UserResult
        exercise_ids = list(obj.exercises.values_list('id', flat=True))
        if not exercise_ids:
            return False
        completed_count = UserResult.objects.filter(
            student=request.user,
            exercise_id__in=exercise_ids,
            is_completed=True,
        ).count()
        return completed_count == len(exercise_ids)

    def update(self, instance, validated_data):
        module_id = validated_data.pop('module_id', None)
        exercises_data = validated_data.pop('exercises', None)
        if module_id is not None:
            instance.module_id = module_id
        instance = super().update(instance, validated_data)
        if exercises_data is not None:
            self._sync_exercises(instance, exercises_data)
        return instance

    @staticmethod
    def _sync_exercises(lesson, exercises_data):
        existing = {str(e.id): e for e in lesson.exercises.all()}
        seen_ids = set()
        for idx, ex_data in enumerate(exercises_data):
            dataset_id = ex_data.pop('dataset_id', None)
            ex_data.setdefault('order', idx)
            ex_id = ex_data.pop('id', None)
            if ex_id and str(ex_id) in existing:
                ex = existing[str(ex_id)]
                for field, val in ex_data.items():
                    setattr(ex, field, val)
                ex.dataset_id = dataset_id
                ex.save()
                seen_ids.add(str(ex_id))
            else:
                LessonExercise.objects.create(
                    lesson=lesson,
                    dataset_id=dataset_id,
                    **ex_data,
                )
        # Delete exercises not present in the payload
        for ex_id, ex in existing.items():
            if ex_id not in seen_ids:
                ex.delete()


class LessonCreateSerializer(serializers.ModelSerializer):
    module_id = serializers.UUIDField(required=True)
    exercises = LessonExerciseSerializer(many=True, required=False)

    class Meta:
        model = Lesson
        fields = [
            'title', 'description', 'lesson_type', 'order',
            'theory_content', 'time_limit_seconds', 'max_attempts',
            'module_id', 'exercises', 'is_published'
        ]

    def validate_module_id(self, value):
        course = self.context.get('course')
        if course and not Module.objects.filter(id=value, course=course).exists():
            raise serializers.ValidationError('Module does not belong to this course.')
        return value

    def create(self, validated_data):
        module_id = validated_data.pop('module_id')
        exercises_data = validated_data.pop('exercises', [])
        lesson = Lesson.objects.create(module_id=module_id, **validated_data)
        for idx, ex_data in enumerate(exercises_data):
            dataset_id = ex_data.pop('dataset_id', None)
            order = ex_data.pop('order', idx)
            LessonExercise.objects.create(
                lesson=lesson,
                order=order,
                dataset_id=dataset_id,
                **ex_data,
            )
        return lesson


class ModuleListSerializer(serializers.ModelSerializer):
    lesson_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Module
        fields = [
            'id', 'title', 'description', 'order',
            'lesson_count', 'is_published', 'created_at',
        ]


class ModuleDetailSerializer(serializers.ModelSerializer):
    lesson_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Module
        fields = [
            'id', 'title', 'description', 'order', 'is_published',
            'lesson_count', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class ModuleCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Module
        fields = ['title', 'description', 'order', 'is_published']


class AttachmentSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.CharField(
        source='uploaded_by.full_name', read_only=True
    )
    download_url = serializers.SerializerMethodField()

    class Meta:
        model = Attachment
        fields = [
            'id', 'lesson', 'assignment', 'file', 'filename',
            'file_type', 'file_size', 'uploaded_by', 'uploaded_by_name',
            'download_url', 'created_at',
        ]
        read_only_fields = [
            'id', 'filename', 'file_type', 'file_size',
            'uploaded_by', 'created_at',
        ]

    def get_download_url(self, obj):
        request = self.context.get('request')
        if request and obj.file:
            return request.build_absolute_uri(obj.file.url)
        return None
