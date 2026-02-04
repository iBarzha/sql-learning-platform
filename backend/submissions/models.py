import uuid
from django.db import models
from django.conf import settings


class Submission(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        RUNNING = 'running', 'Running'
        COMPLETED = 'completed', 'Completed'
        ERROR = 'error', 'Error'
        TIMEOUT = 'timeout', 'Timeout'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='submissions'
    )
    assignment = models.ForeignKey(
        'assignments.Assignment',
        on_delete=models.CASCADE,
        related_name='submissions'
    )
    query = models.TextField(help_text='The submitted SQL query')
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )

    result = models.JSONField(
        null=True,
        blank=True,
        help_text='Query execution result'
    )
    error_message = models.TextField(blank=True)
    execution_time_ms = models.PositiveIntegerField(null=True, blank=True)

    score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    is_correct = models.BooleanField(default=False)
    feedback = models.JSONField(
        default=dict,
        blank=True,
        help_text='Detailed feedback about the submission'
    )

    attempt_number = models.PositiveIntegerField(default=1)
    submitted_at = models.DateTimeField(auto_now_add=True)
    graded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'submissions'
        ordering = ['-submitted_at']
        indexes = [
            models.Index(fields=['student', 'assignment']),
            models.Index(fields=['assignment', 'is_correct']),
        ]

    def __str__(self):
        return f'{self.student.email} - {self.assignment.title} (Attempt {self.attempt_number})'


class UserResult(models.Model):
    """Aggregated results for a user on an assignment."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='results'
    )
    assignment = models.ForeignKey(
        'assignments.Assignment',
        on_delete=models.CASCADE,
        related_name='user_results'
    )
    best_submission = models.ForeignKey(
        Submission,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+'
    )

    best_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    total_attempts = models.PositiveIntegerField(default=0)
    is_completed = models.BooleanField(default=False)
    first_completed_at = models.DateTimeField(null=True, blank=True)
    last_attempt_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'user_results'
        unique_together = ['student', 'assignment']
        ordering = ['-last_attempt_at']

    def __str__(self):
        return f'{self.student.email} - {self.assignment.title}: {self.best_score}'

    def update_from_submission(self, submission):
        """Update result based on a new submission."""
        self.total_attempts += 1
        self.last_attempt_at = submission.submitted_at

        if submission.score and (submission.score > self.best_score):
            self.best_score = submission.score
            self.best_submission = submission

        if submission.is_correct and not self.is_completed:
            self.is_completed = True
            self.first_completed_at = submission.submitted_at

        self.save()
