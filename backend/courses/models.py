import uuid
from django.db import models
from django.conf import settings


class Course(models.Model):
    class DatabaseType(models.TextChoices):
        POSTGRESQL = 'postgresql', 'PostgreSQL'
        MYSQL = 'mysql', 'MySQL'
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
    enrollment_key = models.CharField(max_length=50, blank=True, null=True)
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

    @property
    def student_count(self):
        return self.enrollments.filter(is_active=True).count()

    @property
    def assignment_count(self):
        return self.assignments.count()


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

    def __str__(self):
        return f'{self.student.email} enrolled in {self.course.title}'

    @property
    def is_active(self):
        return self.status == self.Status.ACTIVE


class Dataset(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='datasets'
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
        return f'{self.name} ({self.course.title})'

    def save(self, *args, **kwargs):
        if self.is_default:
            Dataset.objects.filter(course=self.course, is_default=True).update(is_default=False)
        super().save(*args, **kwargs)
