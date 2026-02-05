"""Admin configuration for sandbox models."""

from django.contrib import admin
from django.utils.html import format_html

from .models import SandboxContainer, ExecutionLog, ContainerStatus


@admin.register(SandboxContainer)
class SandboxContainerAdmin(admin.ModelAdmin):
    """Admin view for sandbox containers."""

    list_display = [
        'short_container_id',
        'database_type',
        'status_badge',
        'host',
        'port',
        'executions_count',
        'last_used_at',
        'created_at',
    ]
    list_filter = ['database_type', 'status', 'created_at']
    search_fields = ['container_id', 'host']
    readonly_fields = [
        'id',
        'container_id',
        'created_at',
        'updated_at',
        'executions_count',
        'last_used_at',
    ]
    ordering = ['-created_at']

    def short_container_id(self, obj):
        """Display shortened container ID."""
        return obj.container_id[:12]
    short_container_id.short_description = 'Container ID'

    def status_badge(self, obj):
        """Display status with color badge."""
        colors = {
            ContainerStatus.CREATING: '#FFA500',
            ContainerStatus.READY: '#28A745',
            ContainerStatus.BUSY: '#007BFF',
            ContainerStatus.ERROR: '#DC3545',
            ContainerStatus.STOPPING: '#FFC107',
            ContainerStatus.STOPPED: '#6C757D',
        }
        color = colors.get(obj.status, '#6C757D')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 3px; font-size: 11px;">{}</span>',
            color,
            obj.status.upper()
        )
    status_badge.short_description = 'Status'


@admin.register(ExecutionLog)
class ExecutionLogAdmin(admin.ModelAdmin):
    """Admin view for execution logs."""

    list_display = [
        'short_id',
        'container_type',
        'success_badge',
        'execution_time_ms',
        'query_preview',
        'created_at',
    ]
    list_filter = ['success', 'created_at', 'container__database_type']
    search_fields = ['query', 'error_message']
    readonly_fields = [
        'id',
        'container',
        'user_id',
        'submission_id',
        'query',
        'execution_time_ms',
        'success',
        'error_message',
        'created_at',
    ]
    ordering = ['-created_at']

    def short_id(self, obj):
        """Display shortened ID."""
        return str(obj.id)[:8]
    short_id.short_description = 'ID'

    def container_type(self, obj):
        """Display container database type."""
        return obj.container.database_type if obj.container else '-'
    container_type.short_description = 'DB Type'

    def success_badge(self, obj):
        """Display success with color badge."""
        if obj.success:
            return format_html(
                '<span style="color: #28A745; font-weight: bold;">✓</span>'
            )
        return format_html(
            '<span style="color: #DC3545; font-weight: bold;">✗</span>'
        )
    success_badge.short_description = 'OK'

    def query_preview(self, obj):
        """Display truncated query."""
        query = obj.query[:50]
        if len(obj.query) > 50:
            query += '...'
        return query
    query_preview.short_description = 'Query'
