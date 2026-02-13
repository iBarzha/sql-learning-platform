import random
import string
import uuid
from django.db import models
from django.conf import settings


# Exclude ambiguous characters: O/0/I/1
COURSE_CODE_CHARS = string.ascii_uppercase.replace('O', '').replace('I', '') + string.digits.replace('0', '').replace('1', '')


def generate_course_code(length=6):
    """Generate a random course code (uppercase letters + digits, no ambiguous chars)."""
    while True:
        code = ''.join(random.choices(COURSE_CODE_CHARS, k=length))
        if not Course.objects.filter(course_code=code).exists():
            return code


class Course(models.Model):
    class DatabaseType(models.TextChoices):
        POSTGRESQL = 'postgresql', 'PostgreSQL'
        SQLITE = 'sqlite', 'SQLite'
        MARIADB = 'mariadb', 'MariaDB'
        MONGODB = 'mongodb', 'MongoDB'
        REDIS = 'redis', 'Redis'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    instructor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='courses_teaching'
    )
    database_type = models.CharField(
        max_length=20,
        choices=DatabaseType.choices,
        default=DatabaseType.POSTGRESQL
    )
    is_published = models.BooleanField(default=False)
    course_code = models.CharField(max_length=8, unique=True, editable=False)
    max_students = models.PositiveIntegerField(null=True, blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'courses'
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.course_code:
            self.course_code = generate_course_code()
        super().save(*args, **kwargs)


class Enrollment(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        ACTIVE = 'active', 'Active'
        COMPLETED = 'completed', 'Completed'
        DROPPED = 'dropped', 'Dropped'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='enrollments'
    )
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='enrollments'
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE
    )
    enrolled_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    grade = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    class Meta:
        db_table = 'enrollments'
        unique_together = ['student', 'course']
        ordering = ['-enrolled_at']
        indexes = [
            models.Index(fields=['course', 'status']),
            models.Index(fields=['student', 'status']),
        ]

    def __str__(self):
        return f'{self.student.email} enrolled in {self.course.title}'

    @property
    def is_active(self):
        return self.status == self.Status.ACTIVE


class Module(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='modules'
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'modules'
        ordering = ['order', 'created_at']

    def __str__(self):
        return f'{self.title} ({self.course.title})'


class Lesson(models.Model):
    class LessonType(models.TextChoices):
        THEORY = 'theory', 'Theory'
        PRACTICE = 'practice', 'Practice'
        MIXED = 'mixed', 'Theory & Practice'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='lessons'
    )
    module = models.ForeignKey(
        Module,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='lessons'
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, help_text='Short description shown on card')
    lesson_type = models.CharField(
        max_length=20,
        choices=LessonType.choices,
        default=LessonType.MIXED
    )
    order = models.PositiveIntegerField(default=0)

    # Theory content
    theory_content = models.TextField(blank=True, help_text='Markdown supported')

    # Practice content
    practice_description = models.TextField(blank=True, help_text='Task description')
    practice_initial_code = models.TextField(blank=True, help_text='Initial code template')
    expected_query = models.TextField(blank=True, help_text='Expected SQL query')
    expected_result = models.JSONField(null=True, blank=True)

    # Grading options
    required_keywords = models.JSONField(default=list, blank=True)
    forbidden_keywords = models.JSONField(default=list, blank=True)
    order_matters = models.BooleanField(default=False)
    max_score = models.PositiveIntegerField(default=100)
    time_limit_seconds = models.PositiveIntegerField(default=60)
    max_attempts = models.PositiveIntegerField(null=True, blank=True)

    # Hints
    hints = models.JSONField(default=list, blank=True)

    # Dataset for practice
    dataset = models.ForeignKey(
        'Dataset',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='lessons'
    )

    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'lessons'
        ordering = ['order', 'created_at']

    def __str__(self):
        return f'{self.title} ({self.course.title})'


class Dataset(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    course = models.ForeignKey(
        Course,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='datasets'
    )
    database_type = models.CharField(
        max_length=20,
        choices=Course.DatabaseType.choices,
        default=Course.DatabaseType.SQLITE
    )
    schema_sql = models.TextField(help_text='SQL to create tables and schema')
    seed_sql = models.TextField(blank=True, help_text='SQL to populate initial data')
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'datasets'
        ordering = ['name']

    def __str__(self):
        if self.course:
            return f'{self.name} ({self.course.title})'
        return self.name

    def save(self, *args, **kwargs):
        if self.is_default and self.course:
            Dataset.objects.filter(course=self.course, is_default=True).update(is_default=False)
        super().save(*args, **kwargs)


class Attachment(models.Model):
    class FileType(models.TextChoices):
        PDF = 'pdf', 'PDF'
        IMAGE = 'image', 'Image'
        CODE = 'code', 'Code'
        OTHER = 'other', 'Other'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lesson = models.ForeignKey(
        Lesson,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='attachments'
    )
    assignment = models.ForeignKey(
        'assignments.Assignment',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='attachments'
    )
    file = models.FileField(upload_to='attachments/%Y/%m/')
    filename = models.CharField(max_length=255)
    file_type = models.CharField(
        max_length=20,
        choices=FileType.choices,
        default=FileType.OTHER
    )
    file_size = models.PositiveIntegerField()
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='uploaded_attachments'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'attachments'
        ordering = ['created_at']

    def __str__(self):
        return self.filename
