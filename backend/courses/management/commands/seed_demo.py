"""Load a presentable course for a demo: accounts, lessons of every type, a timed test.

    python manage.py seed_demo            create what is missing
    python manage.py seed_demo --reset    delete the demo courses first
    python manage.py seed_demo --no-history   skip the sample submissions

The password of the demo accounts comes from DEMO_PASSWORD. Existing accounts keep
their password unless --set-passwords is given.
"""

import os

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from courses.models import Course, Dataset, Enrollment, Lesson, LessonExercise, Module
from users.models import User

SQL_COURSE_CODE = 'SQLDEM'
MONGO_COURSE_CODE = 'MNGDEM'

ACCOUNTS = [
    ('admin@test.com', 'Адміністратор', 'Платформи', User.Role.ADMIN),
    ('instructor@test.com', 'Оксана', 'Викладач', User.Role.INSTRUCTOR),
    ('student@test.com', 'Андрій', 'Студент', User.Role.STUDENT),
    ('student2@test.com', 'Марія', 'Новенька', User.Role.STUDENT),
]

SCHEMA = """CREATE TABLE departments (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  city TEXT NOT NULL
);

CREATE TABLE employees (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  dept_id INTEGER REFERENCES departments(id),
  job TEXT NOT NULL,
  salary NUMERIC(10,2) NOT NULL,
  hired DATE NOT NULL
);"""

DEPARTMENTS = [
    (1, 'Розробка', 'Київ'),
    (2, 'Аналітика', 'Львів'),
    (3, 'Підтримка', 'Черкаси'),
]

EMPLOYEES = [
    (1, 'Олена Коваль', 1, 'Розробник', 52000, '2021-03-15'),
    (2, 'Андрій Мельник', 1, 'Тімлід', 78000, '2019-09-01'),
    (3, 'Ірина Шевченко', 2, 'Аналітик', 45000, '2022-01-10'),
    (4, 'Максим Бондар', 2, 'Аналітик', 41000, '2023-06-20'),
    (5, 'Наталія Ткачук', 3, 'Оператор', 28000, '2020-11-05'),
    (6, 'Сергій Лисенко', 3, 'Оператор', 30000, '2024-02-12'),
    (7, 'Юлія Кравець', 1, 'Тестувальник', 39000, '2022-08-22'),
]


def _literal(value):
    if value is None:
        return 'NULL'
    if isinstance(value, (int, float)):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def seed_sql(departments=DEPARTMENTS, employees=EMPLOYEES):
    def rows(items):
        return ',\n'.join('  (' + ', '.join(_literal(v) for v in item) + ')' for item in items)

    return (
        'INSERT INTO departments (id, name, city) VALUES\n' + rows(departments) + ';\n\n'
        'INSERT INTO employees (id, name, dept_id, job, salary, hired) VALUES\n'
        + rows(employees) + ';'
    )


# Hidden datasets: each isolates one mistake the visible data cannot show.
EMPTY_DEPARTMENT = {
    'name': 'Відділ без працівників',
    'targets': 'відділ, у якому немає жодного працівника',
    'seed_sql': seed_sql(departments=DEPARTMENTS + [(4, 'Маркетинг', 'Одеса')]),
}
BOUNDARY_SALARY = {
    'name': 'Гранична зарплата',
    'targets': 'працівник із зарплатою рівно 40 000',
    'seed_sql': seed_sql(employees=EMPLOYEES + [
        (8, 'Богдан Савчук', 2, 'Аналітик', 40000, '2023-01-09'),
    ]),
}
BOUNDARY_DATE = {
    'name': 'Гранична дата',
    'targets': 'працівник, прийнятий рівно 1 січня 2022 року',
    'seed_sql': seed_sql(employees=EMPLOYEES + [
        (8, 'Богдан Савчук', 2, 'Аналітик', 40000, '2022-01-01'),
    ]),
}
OTHER_SALARIES = {
    'name': 'Інші зарплати',
    'targets': 'інший розподіл зарплат: середнє значення не можна вписати числом',
    'seed_sql': seed_sql(employees=[
        (1, 'Олена Коваль', 1, 'Розробник', 20000, '2021-03-15'),
        (2, 'Андрій Мельник', 1, 'Тімлід', 22000, '2019-09-01'),
        (3, 'Ірина Шевченко', 2, 'Аналітик', 24000, '2022-01-10'),
        (4, 'Максим Бондар', 2, 'Аналітик', 90000, '2023-06-20'),
    ]),
}

THEORY_SELECT = """# Вибірка даних: SELECT

Інструкція `SELECT` читає дані з таблиць і нічого в них не змінює.

```sql
SELECT name, salary
FROM employees
WHERE salary > 40000
ORDER BY salary DESC;
```

| Частина | Що робить |
|---|---|
| `SELECT` | перелічує стовпці, які потрібні в результаті |
| `FROM` | вказує таблицю |
| `WHERE` | залишає тільки рядки, що відповідають умові |
| `ORDER BY` | сортує результат, `DESC` означає за спаданням |

## Спробуйте самі

Нижче невелика база прямо в браузері. Змініть запит і натисніть кнопку запуску.

```sql-exercise
{"schema":"CREATE TABLE employees(id INTEGER, name TEXT, job TEXT, salary INTEGER);","seed":"INSERT INTO employees VALUES (1,'Олена Коваль','Розробник',52000),(2,'Андрій Мельник','Тімлід',78000),(3,'Наталія Ткачук','Оператор',28000);","initial":"SELECT name, salary FROM employees WHERE salary > 40000;","hint":"Спробуйте додати ORDER BY salary DESC"}
```

## Що запам'ятати

1. Порядок рядків без `ORDER BY` не гарантований.
2. Умова `salary > 40000` не включає працівника із зарплатою рівно 40 000. Для цього потрібно `>=`.
3. Текстові значення пишуться в одинарних лапках: `WHERE job = 'Аналітик'`.
"""

THEORY_JOIN = """# З'єднання таблиць і групування

Дані про працівників і відділи лежать у різних таблицях. Щоб побачити їх разом, таблиці з'єднують.

## INNER JOIN і LEFT JOIN

```sql
SELECT d.name, e.name
FROM departments d
JOIN employees e ON e.dept_id = d.id;
```

`JOIN` (він же `INNER JOIN`) залишає тільки ті рядки, для яких знайшлася пара.
Відділ без працівників у результат не потрапить.

`LEFT JOIN` залишає всі рядки лівої таблиці. Якщо пари немає, стовпці правої таблиці будуть `NULL`.

## Групування

```sql
SELECT d.name, COUNT(e.id)
FROM departments d
LEFT JOIN employees e ON e.dept_id = d.id
GROUP BY d.id, d.name;
```

Зверніть увагу на `COUNT(e.id)`. Для відділу без працівників `COUNT(*)` поверне 1,
бо рядок відділу існує, а `COUNT(e.id)` поверне 0, бо `e.id` там `NULL`.

Умова на результат групування записується в `HAVING`, а не у `WHERE`.

## Як перевіряється відповідь

Система порівнює результат вашого запиту з результатом еталонного. Перевірка йде
не тільки на даних, які ви бачите, а й на контрольних наборах. Тому запит, який
випадково дає правильну відповідь на видимих даних, повний бал не отримає.
"""

THEORY_TEST = """# Контрольна робота №1

На всі завдання відведено **20 хвилин**. Відлік починається, коли ви відкриєте практичну частину,
і не зупиняється, якщо закрити або оновити сторінку.

На кожне завдання є **3 спроби**, зараховується найкраща. Кожне завдання оцінюється у 20 балів.
"""


def practice_lessons(dataset):
    """(module title, lesson fields, exercises) for the SQL course."""
    return [
        ('Вибірка даних', dict(
            title='Інструкція SELECT',
            description='Як читати дані з таблиці: стовпці, умови, сортування',
            lesson_type='theory', theory_content=THEORY_SELECT,
        ), []),
        ('Вибірка даних', dict(
            title='Вибірка та фільтрація',
            description='Три вправи на SELECT, WHERE та ORDER BY',
            lesson_type='practice',
        ), [
            dict(title='Усі працівники',
                 description='Виведіть імена та посади всіх працівників.',
                 expected_query='SELECT name, job FROM employees',
                 hints=['Потрібні стовпці name та job з таблиці employees.']),
            dict(title='Зарплата понад 40 000',
                 description="Виведіть ім'я та зарплату працівників, які отримують більше 40 000.",
                 expected_query='SELECT name, salary FROM employees WHERE salary > 40000',
                 check_datasets=[BOUNDARY_SALARY],
                 hints=['Умова записується у WHERE.', '«Більше» не включає саме значення 40 000.']),
            dict(title='Рейтинг зарплат',
                 description="Виведіть ім'я та зарплату всіх працівників, "
                             'від найбільшої зарплати до найменшої.',
                 expected_query='SELECT name, salary FROM employees ORDER BY salary DESC',
                 hints=['Сортування за спаданням: ORDER BY ... DESC.']),
        ]),
        ("З'єднання та групування", dict(
            title="З'єднання таблиць і групування",
            description='JOIN, LEFT JOIN, GROUP BY, HAVING: теорія і практика',
            lesson_type='mixed', theory_content=THEORY_JOIN,
        ), [
            dict(title='Працівники та їхні відділи',
                 description="Виведіть ім'я працівника та назву його відділу. "
                             "Використайте з'єднання таблиць.",
                 expected_query='SELECT e.name, d.name FROM employees e '
                                'JOIN departments d ON d.id = e.dept_id',
                 required_keywords=['JOIN']),
            dict(title='Кількість працівників у відділах',
                 description='Для кожного відділу виведіть його назву та кількість працівників. '
                             'Відділи без працівників теж мають бути в результаті, з нулем.',
                 expected_query='SELECT d.name, COUNT(e.id) FROM departments d '
                                'LEFT JOIN employees e ON e.dept_id = d.id GROUP BY d.id, d.name',
                 check_datasets=[EMPTY_DEPARTMENT],
                 hints=['Який вид JOIN зберігає відділи без працівників?']),
            dict(title='Середня зарплата у відділах',
                 description='Виведіть назву відділу та середню зарплату в ньому, округлену '
                             'до двох знаків. Потрібні лише відділи, де середня зарплата '
                             'перевищує 35 000.',
                 expected_query='SELECT d.name, ROUND(AVG(e.salary), 2) FROM departments d '
                                'JOIN employees e ON e.dept_id = d.id '
                                'GROUP BY d.name HAVING AVG(e.salary) > 35000',
                 required_keywords=['GROUP BY', 'HAVING']),
        ]),
        ("З'єднання та групування", dict(
            title='Зміна даних',
            description='INSERT, UPDATE та DELETE: перевіряється стан таблиць після запиту',
            lesson_type='practice',
        ), [
            dict(title='Підвищення зарплати',
                 description='Підвищте на 10% зарплату всім працівникам відділу «Підтримка» '
                             '(id відділу 3).',
                 expected_query='UPDATE employees SET salary = salary * 1.10 WHERE dept_id = 3'),
            dict(title='Новий відділ',
                 description='Додайте відділ «Маркетинг» у місті Одеса з id = 4.',
                 expected_query="INSERT INTO departments (id, name, city) "
                                "VALUES (4, 'Маркетинг', 'Одеса')"),
            dict(title='Звільнення',
                 description='Видаліть працівників, прийнятих на роботу до 2020 року.',
                 expected_query="DELETE FROM employees WHERE hired < '2020-01-01'"),
        ]),
        ('Контроль знань', dict(
            title='Контрольна робота №1',
            description='20 хвилин, 5 завдань по 20 балів, 3 спроби на завдання',
            lesson_type='mixed', theory_content=THEORY_TEST,
            time_limit_seconds=20 * 60, max_attempts=3,
        ), [
            dict(title='Нові працівники', max_score=20,
                 description="Виведіть ім'я та дату прийому працівників, прийнятих у 2022 році "
                             'або пізніше, від найновіших до найдавніших.',
                 expected_query="SELECT name, hired FROM employees "
                                "WHERE hired >= '2022-01-01' ORDER BY hired DESC",
                 check_datasets=[BOUNDARY_DATE]),
            dict(title='Найбільша зарплата у відділі', max_score=20,
                 description='Виведіть назву кожного відділу та найбільшу зарплату в ньому. '
                             'Відділи без працівників теж мають бути в результаті.',
                 expected_query='SELECT d.name, MAX(e.salary) FROM departments d '
                                'LEFT JOIN employees e ON e.dept_id = d.id GROUP BY d.id, d.name',
                 check_datasets=[EMPTY_DEPARTMENT]),
            dict(title='Великі відділи', max_score=20,
                 description='Виведіть назви відділів, у яких працює щонайменше три працівники.',
                 expected_query='SELECT d.name FROM departments d '
                                'JOIN employees e ON e.dept_id = d.id '
                                'GROUP BY d.id, d.name HAVING COUNT(*) >= 3',
                 required_keywords=['HAVING']),
            dict(title='Вище середнього', max_score=20,
                 description='Виведіть імена працівників, які отримують більше за середню '
                             'зарплату по компанії.',
                 expected_query='SELECT name FROM employees '
                                'WHERE salary > (SELECT AVG(salary) FROM employees)',
                 check_datasets=[OTHER_SALARIES]),
            dict(title='Переведення', max_score=20,
                 description='Переведіть усіх працівників відділу «Аналітика» (id 2) '
                             'до відділу «Розробка» (id 1).',
                 expected_query='UPDATE employees SET dept_id = 1 WHERE dept_id = 2'),
        ]),
    ]


MONGO_SEED = """db.products.insertMany([
  { name: "Ноутбук", category: "Електроніка", price: 32000, stock: 12 },
  { name: "Навушники", category: "Електроніка", price: 1800, stock: 40 },
  { name: "Монітор", category: "Електроніка", price: 7400, stock: 9 },
  { name: "Стілець", category: "Меблі", price: 4200, stock: 15 },
  { name: "Стіл", category: "Меблі", price: 6900, stock: 7 },
  { name: "Блокнот", category: "Канцелярія", price: 120, stock: 300 }
]);"""

MONGO_EXERCISES = [
    dict(title='Дешеві товари',
         description='Знайдіть усі товари, дешевші за 5000.',
         expected_query='db.products.find({ price: { $lt: 5000 } })',
         hints=['Оператор порівняння «менше» у MongoDB: $lt.']),
    dict(title='Товари за категоріями',
         description='Порахуйте кількість товарів у кожній категорії.',
         expected_query='db.products.aggregate([{ $group: { _id: "$category", '
                        'count: { $sum: 1 } } }])',
         hints=['Групування виконує стадія $group.']),
]

# Sample answers of student@test.com, so the gradebook is not empty on first login.
HISTORY = [
    ('Вибірка та фільтрація', 'Усі працівники', 'SELECT name, job FROM employees'),
    ('Вибірка та фільтрація', 'Зарплата понад 40 000',
     'SELECT name, salary FROM employees WHERE salary >= 40000'),
    ('Вибірка та фільтрація', 'Зарплата понад 40 000',
     'SELECT name, salary FROM employees WHERE salary > 40000'),
    ('Вибірка та фільтрація', 'Рейтинг зарплат',
     'SELECT name, salary FROM employees ORDER BY salary'),
    ("З'єднання таблиць і групування", 'Кількість працівників у відділах',
     'SELECT d.name, COUNT(e.id) FROM departments d '
     'JOIN employees e ON e.dept_id = d.id GROUP BY d.id, d.name'),
]


class Command(BaseCommand):
    help = 'Create demo accounts and a demo course with lessons of every type.'

    def add_arguments(self, parser):
        parser.add_argument('--reset', action='store_true',
                            help='Delete the demo courses before creating them again.')
        parser.add_argument('--no-history', action='store_true',
                            help='Do not create sample submissions.')
        parser.add_argument('--set-passwords', action='store_true',
                            help='Also set DEMO_PASSWORD on accounts that already exist.')

    def handle(self, *args, **options):
        password = os.getenv('DEMO_PASSWORD', '').strip()
        users = self._accounts(password, options['set_passwords'])

        call_command('seed_sandbox_datasets', verbosity=0)

        if options['reset']:
            deleted, _ = Course.objects.filter(
                course_code__in=[SQL_COURSE_CODE, MONGO_COURSE_CODE]).delete()
            self.stdout.write(f'Removed the previous demo courses ({deleted} rows).')

        instructor = users['instructor@test.com']
        with transaction.atomic():
            sql_course, sql_created = self._sql_course(instructor)
            self._mongo_course(instructor)

        student = users['student@test.com']
        Enrollment.objects.get_or_create(student=student, course=sql_course)

        if sql_created and not options['no_history']:
            self._history(student, sql_course)

        self.stdout.write(self.style.SUCCESS('Demo data is ready.'))
        self.stdout.write(f'  SQL course code:     {SQL_COURSE_CODE}')
        self.stdout.write(f'  MongoDB course code: {MONGO_COURSE_CODE}')
        for email, _, _, role in ACCOUNTS:
            self.stdout.write(f'  {role:<11} {email}')
        self.stdout.write('  student2@test.com is not enrolled: use it to show joining by code.')

    def _accounts(self, password, overwrite):
        users = {}
        for email, first_name, last_name, role in ACCOUNTS:
            user = User.objects.filter(email=email).first()
            if user is None:
                if not password:
                    raise CommandError(
                        'DEMO_PASSWORD is not set, cannot create the demo accounts.')
                is_admin = role == User.Role.ADMIN
                user = User.objects.create_user(
                    email=email, password=password, first_name=first_name,
                    last_name=last_name, role=role,
                    is_staff=is_admin, is_superuser=is_admin,
                )
            elif overwrite and password:
                user.set_password(password)
                user.must_change_password = False
                user.save(update_fields=['password', 'must_change_password'])
            users[email] = user
        return users

    def _sql_course(self, instructor):
        course = Course.objects.filter(course_code=SQL_COURSE_CODE).first()
        if course is not None:
            return course, False

        course = Course(
            title='Бази даних: мова SQL',
            description='Вибірка, фільтрація, з\'єднання таблиць, групування та зміна даних. '
                        'Практичні завдання перевіряються автоматично.',
            instructor=instructor, database_type='postgresql', is_published=True,
        )
        course.course_code = SQL_COURSE_CODE
        course.save()

        dataset = Dataset.objects.create(
            name='Компанія', description='Відділи та працівники',
            course=course, created_by=instructor, database_type='postgresql',
            schema_sql=SCHEMA, seed_sql=seed_sql(), is_default=True,
        )
        self._lessons(course, dataset, practice_lessons(dataset))
        return course, True

    def _mongo_course(self, instructor):
        if Course.objects.filter(course_code=MONGO_COURSE_CODE).exists():
            return
        course = Course(
            title='MongoDB: документні бази',
            description='Пошук та агрегація документів. Показує, що перевірка працює '
                        'і для нереляційних баз.',
            instructor=instructor, database_type='mongodb', is_published=True,
        )
        course.course_code = MONGO_COURSE_CODE
        course.save()

        dataset = Dataset.objects.create(
            name='Каталог товарів', description='Товари інтернет-магазину',
            course=course, created_by=instructor, database_type='mongodb',
            schema_sql='', seed_sql=MONGO_SEED, is_default=True,
        )
        self._lessons(course, dataset, [
            ('Запити до документів', dict(
                title='Пошук та агрегація',
                description='find та aggregate на колекції товарів',
                lesson_type='practice',
            ), MONGO_EXERCISES),
        ])

    def _lessons(self, course, dataset, lessons):
        modules = {}
        for order, (module_title, fields, exercises) in enumerate(lessons):
            module = modules.get(module_title)
            if module is None:
                module = Module.objects.create(
                    course=course, title=module_title, order=len(modules), is_published=True)
                modules[module_title] = module
            lesson = Lesson.objects.create(
                course=course, module=module, order=order, is_published=True, **fields)
            for index, exercise in enumerate(exercises):
                LessonExercise.objects.create(
                    lesson=lesson, order=index, dataset=dataset, **exercise)

    def _history(self, student, course):
        """Submit through the real API, so the scores are produced by the grading core."""
        from rest_framework.test import APIClient

        allowed = [h for h in settings.ALLOWED_HOSTS if h and h != '*']
        client = APIClient(HTTP_HOST=allowed[0] if allowed else 'localhost')
        client.force_authenticate(student)

        for lesson_title, exercise_title, query in HISTORY:
            exercise = LessonExercise.objects.filter(
                lesson__course=course, lesson__title=lesson_title, title=exercise_title).first()
            if exercise is None:
                continue
            response = client.post(
                f'/api/courses/{course.id}/lessons/{exercise.lesson_id}/submissions/',
                {'query': query, 'exercise_id': str(exercise.id)}, format='json')
            if response.status_code == 201:
                self.stdout.write(
                    f'  {exercise_title}: {response.data.get("score")} / {exercise.max_score}')
            else:
                self.stdout.write(self.style.WARNING(
                    f'  {exercise_title}: sample answer was not accepted '
                    f'({response.status_code})'))
