import random
import string

from django.db import migrations, models

COURSE_CODE_CHARS = (
    string.ascii_uppercase.replace('O', '').replace('I', '')
    + string.digits.replace('0', '').replace('1', '')
)


def generate_code(length=6):
    return ''.join(random.choices(COURSE_CODE_CHARS, k=length))


def populate_course_codes(apps, schema_editor):
    Course = apps.get_model('courses', 'Course')
    used_codes = set()
    # Generate codes for ALL courses (replace any old enrollment_key values)
    for course in Course.objects.all():
        code = generate_code()
        while code in used_codes or Course.objects.filter(course_code=code).exclude(pk=course.pk).exists():
            code = generate_code()
        course.course_code = code
        course.save(update_fields=['course_code'])
        used_codes.add(code)


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0006_dataset_standalone'),
    ]

    operations = [
        # Step 1: Rename the field (keeps old max_length=50)
        migrations.RenameField(
            model_name='course',
            old_name='enrollment_key',
            new_name='course_code',
        ),
        # Step 2: Populate ALL rows with short 6-char codes (still varchar(50))
        migrations.RunPython(populate_course_codes, migrations.RunPython.noop),
        # Step 3: Now safe to shrink to max_length=8
        migrations.AlterField(
            model_name='course',
            name='course_code',
            field=models.CharField(max_length=8, default='', editable=False),
        ),
        # Step 4: Add unique constraint
        migrations.AlterField(
            model_name='course',
            name='course_code',
            field=models.CharField(max_length=8, unique=True, editable=False),
        ),
    ]
