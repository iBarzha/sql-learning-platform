from django.contrib import admin
from .models import Submission, UserResult


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = ('student', 'assignment', 'status', 'score', 'is_correct', 'attempt_number', 'submitted_at')
    list_filter = ('status', 'is_correct')
    search_fields = ('student__email', 'assignment__title')
    raw_id_fields = ('student', 'assignment')
    date_hierarchy = 'submitted_at'
    readonly_fields = ('submitted_at', 'graded_at')


@admin.register(UserResult)
class UserResultAdmin(admin.ModelAdmin):
    list_display = ('student', 'assignment', 'best_score', 'total_attempts', 'is_completed', 'last_attempt_at')
    list_filter = ('is_completed',)
    search_fields = ('student__email', 'assignment__title')
    raw_id_fields = ('student', 'assignment', 'best_submission')
