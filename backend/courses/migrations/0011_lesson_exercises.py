import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0010_lesson_module_required'),
    ]

    operations = [
        # Lesson keeps theory + lesson-wide practice settings; per-task fields move to LessonExercise.
        migrations.RemoveField(model_name='lesson', name='practice_description'),
        migrations.RemoveField(model_name='lesson', name='practice_initial_code'),
        migrations.RemoveField(model_name='lesson', name='expected_query'),
        migrations.RemoveField(model_name='lesson', name='expected_result'),
        migrations.RemoveField(model_name='lesson', name='required_keywords'),
        migrations.RemoveField(model_name='lesson', name='forbidden_keywords'),
        migrations.RemoveField(model_name='lesson', name='order_matters'),
        migrations.RemoveField(model_name='lesson', name='max_score'),
        migrations.RemoveField(model_name='lesson', name='hints'),
        migrations.RemoveField(model_name='lesson', name='dataset'),
        migrations.AlterField(
            model_name='lesson',
            name='time_limit_seconds',
            field=models.PositiveIntegerField(
                default=600,
                help_text='Total time for all practice exercises in this lesson',
            ),
        ),
        migrations.AlterField(
            model_name='lesson',
            name='max_attempts',
            field=models.PositiveIntegerField(
                blank=True,
                null=True,
                help_text='Per-exercise attempt limit (null = unlimited)',
            ),
        ),
        migrations.CreateModel(
            name='LessonExercise',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('order', models.PositiveIntegerField(default=0)),
                ('title', models.CharField(default='Exercise', max_length=255)),
                ('description', models.TextField(blank=True, help_text='Task description')),
                ('initial_code', models.TextField(blank=True, help_text='Initial code template')),
                ('expected_query', models.TextField(blank=True, help_text='Expected SQL query')),
                ('expected_result', models.JSONField(blank=True, null=True)),
                ('required_keywords', models.JSONField(blank=True, default=list)),
                ('forbidden_keywords', models.JSONField(blank=True, default=list)),
                ('order_matters', models.BooleanField(default=False)),
                ('max_score', models.PositiveIntegerField(default=100)),
                ('hints', models.JSONField(blank=True, default=list)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('dataset', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='exercises',
                    to='courses.dataset',
                )),
                ('lesson', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='exercises',
                    to='courses.lesson',
                )),
            ],
            options={
                'db_table': 'lesson_exercises',
                'ordering': ['order', 'created_at'],
            },
        ),
    ]
