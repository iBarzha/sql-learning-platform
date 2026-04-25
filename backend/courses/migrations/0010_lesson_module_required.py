from django.db import migrations, models
import django.db.models.deletion


def delete_orphan_lessons(apps, schema_editor):
    """Delete lessons without a module assignment (test data only).

    This is required because the module FK is becoming non-nullable. Per project
    decision, no production data exists, so dropping orphans is safe.
    """
    Lesson = apps.get_model('courses', 'Lesson')
    Lesson.objects.filter(module__isnull=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0009_dataset_quick_start_queries'),
    ]

    operations = [
        migrations.RunPython(delete_orphan_lessons, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='lesson',
            name='module',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='lessons',
                to='courses.module',
            ),
        ),
    ]
