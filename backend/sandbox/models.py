"""Models for sandbox container tracking."""

import uuid
from django.db import models


class ContainerStatus(models.TextChoices):
    """Status of a sandbox container."""
    CREATING = 'creating', 'Creating'
    READY = 'ready', 'Ready'
    BUSY = 'busy', 'Busy'
    ERROR = 'error', 'Error'
    STOPPING = 'stopping', 'Stopping'
    STOPPED = 'stopped', 'Stopped'


class SandboxContainer(models.Model):
    """Track sandbox containers for monitoring and cleanup."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    container_id = models.CharField(max_length=64, unique=True, db_index=True)
    database_type = models.CharField(max_length=20, db_index=True)
    status = models.CharField(
        max_length=20,
        choices=ContainerStatus.choices,
        default=ContainerStatus.CREATING
    )

    # Connection info
    host = models.CharField(max_length=255)
    port = models.PositiveIntegerField()

    # Dataset currently loaded
    dataset_id = models.UUIDField(null=True, blank=True)

    # Stats
    executions_count = models.PositiveIntegerField(default=0)
    last_used_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'sandbox_containers'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.database_type}:{self.container_id[:12]} ({self.status})'


class ExecutionLog(models.Model):
    """Log query executions for debugging and analytics."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    container = models.ForeignKey(
        SandboxContainer,
        on_delete=models.SET_NULL,
        null=True,
        related_name='executions'
    )
    user_id = models.UUIDField(null=True, blank=True)
    submission_id = models.UUIDField(null=True, blank=True)

    query = models.TextField()
    execution_time_ms = models.PositiveIntegerField()
    success = models.BooleanField()
    error_message = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'sandbox_execution_logs'
        ordering = ['-created_at']
