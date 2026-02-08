"""Make Dataset standalone: nullable course FK + own database_type field."""

from django.db import migrations, models
import django.db.models.deletion


def populate_dataset_database_type(apps, schema_editor):
    """Copy database_type from course to dataset for existing records."""
    Dataset = apps.get_model('courses', 'Dataset')
    for dataset in Dataset.objects.select_related('course').all():
        if dataset.course:
            dataset.database_type = dataset.course.database_type
            dataset.save(update_fields=['database_type'])


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0005_replace_mysql_with_sqlite'),
    ]

    operations = [
        # Add database_type field to Dataset with default
        migrations.AddField(
            model_name='dataset',
            name='database_type',
            field=models.CharField(
                choices=[
                    ('postgresql', 'PostgreSQL'),
                    ('sqlite', 'SQLite'),
                    ('mariadb', 'MariaDB'),
                    ('mongodb', 'MongoDB'),
                    ('redis', 'Redis'),
                ],
                default='sqlite',
                max_length=20,
            ),
        ),
        # Populate database_type from course before making course nullable
        migrations.RunPython(
            populate_dataset_database_type,
            migrations.RunPython.noop,
        ),
        # Make course ForeignKey nullable
        migrations.AlterField(
            model_name='dataset',
            name='course',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='datasets',
                to='courses.course',
            ),
        ),
    ]
