import uuid
from django.db import models


class Assignment(models.Model):
    class Difficulty(models.TextChoices):
        EASY = 'easy', 'Easy'
        MEDIUM = 'medium', 'Medium'
        HARD = 'hard', 'Hard'

    class QueryType(models.TextChoices):
        SELECT = 'select', 'SELECT'
        INSERT = 'insert', 'INSERT'
        UPDATE = 'update', 'UPDATE'
        DELETE = 'delete', 'DELETE'
        DDL = 'ddl', 'DDL'
        NOSQL = 'nosql', 'NoSQL'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    course = models.ForeignKey(
        'courses.Course',
        on_delete=models.CASCADE,
        related_name='assignments'
    )
    module = models.ForeignKey(
        'courses.Module',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='assignments'
    )
    dataset = models.ForeignKey(
        'courses.Dataset',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assignments'
    )
    title = models.CharField(max_length=255)
    description = models.TextField()
    instructions = models.TextField(blank=True, help_text='Additional instructions for the student')

    query_type = models.CharField(
        max_length=20,
        choices=QueryType.choices,
        default=QueryType.SELECT
    )
    difficulty = models.CharField(
        max_length=20,
        choices=Difficulty.choices,
        default=Difficulty.EASY
    )

    expected_query = models.TextField(help_text='The correct SQL query')
    expected_result = models.JSONField(
        null=True,
        blank=True,
        help_text='Expected query result for comparison'
    )

    required_keywords = models.JSONField(
        default=list,
        blank=True,
        help_text='Keywords that must be present in the query (e.g., ["JOIN", "GROUP BY"])'
    )
    forbidden_keywords = models.JSONField(
        default=list,
        blank=True,
        help_text='Keywords that must not be present in the query'
    )

    order_matters = models.BooleanField(
        default=False,
        help_text='Whether row order matters in result comparison'
    )
    partial_match = models.BooleanField(
        default=False,
        help_text='Allow partial column matches'
    )

    max_score = models.PositiveIntegerField(default=100)
    time_limit_seconds = models.PositiveIntegerField(
        default=30,
        help_text='Maximum execution time for the query'
    )
    max_attempts = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text='Maximum number of submission attempts (null = unlimited)'
    )

    hints = models.JSONField(
        default=list,
        blank=True,
        help_text='Hints to show after failed attempts'
    )

    due_date = models.DateTimeField(null=True, blank=True)
    is_published = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'assignments'
        ordering = ['order', 'created_at']

    def __str__(self):
        return f'{self.title} ({self.course.title})'
