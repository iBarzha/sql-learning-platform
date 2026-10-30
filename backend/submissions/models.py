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
        related_name='submissions',
        null=True,
        blank=True
    )
    lesson = models.ForeignKey(
        'courses.Lesson',
        on_delete=models.CASCADE,
        related_name='submissions',
        null=True,
        blank=True
    )
    exercise = models.ForeignKey(
        'courses.LessonExercise',
        on_delete=models.CASCADE,
        related_name='submissions',
        null=True,
        blank=True
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
            models.Index(fields=['student', 'lesson']),
            models.Index(fields=['assignment', 'is_correct']),
            models.Index(fields=['lesson', 'is_correct']),
            models.Index(fields=['student', 'assignment', '-submitted_at']),
            models.Index(fields=['status']),
            models.Index(fields=['student', '-submitted_at']),
        ]

    def __str__(self):
        target = self.lesson.title if self.lesson else (self.assignment.title if self.assignment else 'Unknown')
        return f'{self.student.email} - {target} (Attempt {self.attempt_number})'


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
        related_name='user_results',
        null=True,
        blank=True
    )
    lesson = models.ForeignKey(
        'courses.Lesson',
        on_delete=models.CASCADE,
        related_name='user_results',
        null=True,
        blank=True
    )
    exercise = models.ForeignKey(
        'courses.LessonExercise',
        on_delete=models.CASCADE,
        related_name='user_results',
        null=True,
        blank=True
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
    # Lesson-level row (exercise=NULL): when the student first opened the practice.
    # The lesson's time limit is counted from here, server-side.
    started_at = models.DateTimeField(null=True, blank=True)
    # Extra time an instructor granted on top of the lesson's limit (lesson-level row).
    extra_seconds = models.PositiveIntegerField(default=0)

    # An instructor's override of the automatic score, with the reason shown to the student.
    manual_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    manual_comment = models.TextField(blank=True)
    manual_set_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+'
    )
    manual_set_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'user_results'
        ordering = ['-last_attempt_at']
        indexes = [
            models.Index(fields=['student', 'assignment']),
            models.Index(fields=['student', 'lesson']),
            models.Index(fields=['student', 'exercise']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['student', 'assignment'],
                condition=models.Q(assignment__isnull=False),
                name='unique_student_assignment_result',
            ),
            models.UniqueConstraint(
                fields=['student', 'lesson'],
                condition=models.Q(lesson__isnull=False) & models.Q(exercise__isnull=True),
                name='unique_student_lesson_result',
            ),
            models.UniqueConstraint(
                fields=['student', 'exercise'],
                condition=models.Q(exercise__isnull=False),
                name='unique_student_exercise_result',
            ),
        ]

    def __str__(self):
        target = self.lesson.title if self.lesson else (self.assignment.title if self.assignment else 'Unknown')
        return f'{self.student.email} - {target}: {self.best_score}'

    @property
    def effective_score(self):
        """The score that counts: the instructor's manual score when set, else the best one."""
        return self.manual_score if self.manual_score is not None else self.best_score

    @property
    def max_score(self):
        """Maximum score of the task this result belongs to; None for the lesson timer row."""
        if self.exercise_id:
            return self.exercise.max_score
        if self.assignment_id:
            return self.assignment.max_score
        return None

    def update_from_submission(self, submission):
        """Update result based on a new submission (atomic).

        The new best and the first completion are decided by the database, not by the
        values loaded before grading began: a regrade may have lowered them meanwhile.
        A tie never replaces the best answer, and a zero or missing score never becomes it.
        """
        from django.db import transaction
        from django.db.models import F

        rows = UserResult.objects.filter(pk=self.pk)
        with transaction.atomic():
            rows.update(
                total_attempts=F('total_attempts') + 1,
                last_attempt_at=submission.submitted_at,
            )
            if submission.score:
                rows.filter(best_score__lt=submission.score).update(
                    best_score=submission.score,
                    best_submission=submission,
                )
            if submission.is_correct:
                rows.filter(is_completed=False).update(
                    is_completed=True,
                    first_completed_at=submission.submitted_at,
                )
        self.refresh_from_db()
