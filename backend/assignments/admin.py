from django.contrib import admin
from .models import Assignment


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ('title', 'course', 'query_type', 'difficulty', 'is_published', 'due_date', 'order')
    list_filter = ('query_type', 'difficulty', 'is_published')
    search_fields = ('title', 'description')
    raw_id_fields = ('course', 'dataset')
    date_hierarchy = 'created_at'
    ordering = ('course', 'order')
