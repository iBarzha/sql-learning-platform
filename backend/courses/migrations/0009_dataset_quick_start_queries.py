from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0008_attachment_module_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='dataset',
            name='quick_start_queries',
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text='Mapping of example key to query string, e.g. {"basicSelect": "SELECT * FROM artists;"}',
            ),
        ),
    ]
