from django.contrib import admin
from .models import Course, Enrollment, Dataset


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('title', 'instructor', 'database_type', 'is_published', 'student_count', 'created_at')
    list_filter = ('database_type', 'is_published')
    search_fields = ('title', 'description')
    raw_id_fields = ('instructor',)
    date_hierarchy = 'created_at'


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ('student', 'course', 'status', 'grade', 'enrolled_at')
    list_filter = ('status',)
    search_fields = ('student__email', 'course__title')
    raw_id_fields = ('student', 'course')


@admin.register(Dataset)
class DatasetAdmin(admin.ModelAdmin):
    list_display = ('name', 'course', 'is_default', 'created_at')
    list_filter = ('is_default',)
    search_fields = ('name', 'description')
    raw_id_fields = ('course',)
