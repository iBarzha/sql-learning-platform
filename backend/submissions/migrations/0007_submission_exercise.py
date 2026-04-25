import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0011_lesson_exercises'),
        ('submissions', '0006_add_status_and_student_submitted_at_indexes'),
    ]

    operations = [
        migrations.AddField(
            model_name='submission',
            name='exercise',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='submissions',
                to='courses.lessonexercise',
            ),
        ),
        migrations.AddField(
            model_name='userresult',
            name='exercise',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='user_results',
                to='courses.lessonexercise',
            ),
        ),
        migrations.AddIndex(
            model_name='userresult',
            index=models.Index(fields=['student', 'exercise'], name='user_result_student_exercise_idx'),
        ),
        migrations.RemoveConstraint(
            model_name='userresult',
            name='unique_student_lesson_result',
        ),
        migrations.AddConstraint(
            model_name='userresult',
            constraint=models.UniqueConstraint(
                fields=['student', 'lesson'],
                condition=models.Q(('lesson__isnull', False)) & models.Q(('exercise__isnull', True)),
                name='unique_student_lesson_result',
            ),
        ),
        migrations.AddConstraint(
            model_name='userresult',
            constraint=models.UniqueConstraint(
                fields=['student', 'exercise'],
                condition=models.Q(('exercise__isnull', False)),
                name='unique_student_exercise_result',
            ),
        ),
    ]
