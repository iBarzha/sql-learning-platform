"""End-to-end grading flow through the REST API on an in-memory SQLite sandbox.

Instructor creates a course, dataset, module and lesson with exercises; a student
joins by code and submits answers; scores, feedback and aggregates are asserted.
"""

from decimal import Decimal

from rest_framework import status
from rest_framework.test import APITestCase

from assignments.models import Assignment
from courses.models import Course, Lesson, Module
from submissions.models import Submission, UserResult
from users.models import User

SCHEMA = """
CREATE TABLE departments (id INTEGER PRIMARY KEY, name TEXT);
CREATE TABLE employees (
    id INTEGER PRIMARY KEY, name TEXT, dept_id INTEGER, salary REAL, bonus REAL
);
"""
DEPTS = "INSERT INTO departments VALUES (1,'Розробка'),(2,'Аналітика'),(3,'Підтримка');"
EMPS = """
INSERT INTO employees VALUES
 (1,'Іваненко',1,6000,500),(2,'Петренко',1,4000,300),(3,'Коваленко',2,7000,800),
 (4,'Шевченко',3,3000,200),(5,'Бондаренко',2,5500,400);
"""
SEED = DEPTS + EMPS

EMPTY_DEPT_SEED = DEPTS + "INSERT INTO departments VALUES (4,'Кадри');" + EMPS
BOUNDARY_SEED = SEED + "INSERT INTO employees VALUES (8,'Ткаченко',1,5000,150);"

COUNT_PER_DEPT = ("SELECT d.name, COUNT(e.id) FROM departments d "
                  "LEFT JOIN employees e ON e.dept_id = d.id GROUP BY d.name")
BY_SALARY_DESC = 'SELECT name FROM employees ORDER BY salary DESC'


class GradingFlowTestCase(APITestCase):
    def setUp(self):
        self.instructor = User.objects.create_user(
            email='teacher@test.com', password='x', role=User.Role.INSTRUCTOR,
            first_name='Викладач', last_name='Тестовий')
        self.student = User.objects.create_user(
            email='student@test.com', password='x', role=User.Role.STUDENT,
            first_name='Студент', last_name='Тестовий')
        self.outsider = User.objects.create_user(
            email='other@test.com', password='x', role=User.Role.STUDENT,
            first_name='Чужий', last_name='Студент')

        self.as_instructor()
        self.course_id = self.create_course()
        self.dataset_id = self.create_dataset()
        self.module_id = self.create_module()
        self.lesson = self.create_lesson()
        self.exercises = list(self.lesson.exercises.order_by('order'))

        self.as_student()
        self.join_course()

    # ── helpers ─────────────────────────────────────────────────────────

    def as_instructor(self):
        self.client.force_authenticate(self.instructor)

    def as_student(self, user=None):
        self.client.force_authenticate(user or self.student)

    def create_course(self):
        resp = self.client.post('/api/courses/', {
            'title': 'Бази даних', 'description': 'тест',
            'database_type': 'sqlite', 'is_published': True,
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        return resp.data['id']

    def create_dataset(self):
        resp = self.client.post(f'/api/courses/{self.course_id}/datasets/', {
            'name': 'Компанія', 'database_type': 'sqlite',
            'schema_sql': SCHEMA, 'seed_sql': SEED,
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        return resp.data['id']

    def create_module(self):
        resp = self.client.post(f'/api/courses/{self.course_id}/modules/', {
            'title': 'Модуль 1', 'is_published': True,
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        return str(Module.objects.get(course_id=self.course_id, title='Модуль 1').id)

    def create_lesson(self, title='Урок 1', max_attempts=None, exercises=None):
        payload = {
            'title': title, 'lesson_type': 'practice', 'module_id': self.module_id,
            'is_published': True, 'time_limit_seconds': 600, 'max_attempts': max_attempts,
            'exercises': exercises if exercises is not None else [
                {
                    'title': 'Кількість працівників у кожному відділі',
                    'expected_query': COUNT_PER_DEPT,
                    'dataset_id': self.dataset_id,
                    'required_keywords': ['LEFT JOIN'],
                    'check_datasets': [
                        {'name': 'порожній відділ', 'seed_sql': EMPTY_DEPT_SEED,
                         'targets': 'відділ без працівників'},
                    ],
                },
                {
                    'title': 'Прізвища за спаданням зарплати',
                    'expected_query': BY_SALARY_DESC,
                    'dataset_id': self.dataset_id,
                },
            ],
        }
        resp = self.client.post(f'/api/courses/{self.course_id}/lessons/', payload,
                                format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        return Lesson.objects.get(course_id=self.course_id, title=title)

    def join_course(self):
        code = Course.objects.get(id=self.course_id).course_code
        resp = self.client.post('/api/courses/join/', {'code': code}, format='json')
        self.assertIn(resp.status_code, (200, 201), resp.data)

    def submit(self, query, exercise=None, lesson=None):
        lesson = lesson or self.lesson
        exercise = exercise or self.exercises[0]
        return self.client.post(
            f'/api/courses/{self.course_id}/lessons/{lesson.id}/submissions/',
            {'query': query, 'exercise_id': str(exercise.id)}, format='json')

    # ── visibility ──────────────────────────────────────────────────────

    def test_student_never_receives_the_reference_answer(self):
        resp = self.client.get(f'/api/courses/{self.course_id}/lessons/{self.lesson.id}/')
        self.assertEqual(resp.status_code, 200)
        for exercise in resp.data['exercises']:
            self.assertNotIn('expected_query', exercise)
            self.assertNotIn('expected_result', exercise)
            self.assertNotIn('check_datasets', exercise)
        self.assertEqual(len(resp.data['exercises']), 2)

    def test_instructor_receives_the_reference_answer(self):
        self.as_instructor()
        resp = self.client.get(f'/api/courses/{self.course_id}/lessons/{self.lesson.id}/')
        self.assertEqual(resp.data['exercises'][0]['expected_query'], COUNT_PER_DEPT)
        self.assertEqual(len(resp.data['exercises'][0]['check_datasets']), 1)

    # ── grading ─────────────────────────────────────────────────────────

    def test_correct_answer_with_aliases_gets_full_score(self):
        resp = self.submit(
            "SELECT dep.name AS відділ, COUNT(emp.id) AS n FROM departments dep "
            "LEFT JOIN employees emp ON emp.dept_id = dep.id GROUP BY dep.name")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertTrue(resp.data['is_correct'])
        self.assertEqual(Decimal(resp.data['score']), Decimal('100.00'))
        self.assertEqual(resp.data['status'], 'completed')
        self.assertTrue(resp.data['feedback']['result_match'])
        self.assertEqual(resp.data['feedback']['datasets_checked'], 2)
        self.assertEqual(resp.data['result']['columns'], ['відділ', 'n'])
        self.assertEqual(resp.data['result']['row_count'], 3)

    def test_inner_join_is_caught_by_hidden_dataset(self):
        resp = self.submit("SELECT d.name, COUNT(e.id) FROM departments d "
                           "JOIN employees e ON e.dept_id = d.id GROUP BY d.name")
        self.assertFalse(resp.data['is_correct'])
        # Two failed criteria (the hidden dataset and the required LEFT JOIN): no score.
        self.assertEqual(Decimal(resp.data['score']), Decimal('0.00'))
        fb = resp.data['feedback']
        self.assertEqual(fb['passed_count'], fb['total'] - 2)
        self.assertEqual(fb['keywords_missing'], ['LEFT JOIN'])
        self.assertEqual(resp.data['feedback']['failed_datasets'][0]['name'], 'порожній відділ')
        self.assertTrue(any('відділ без працівників' in h for h in resp.data['feedback']['hints']))

    def test_hardcoded_answer_scores_zero(self):
        resp = self.submit("SELECT 'Розробка', 2 UNION ALL SELECT 'Аналітика', 2 "
                           "UNION ALL SELECT 'Підтримка', 1")
        self.assertFalse(resp.data['is_correct'])
        self.assertEqual(Decimal(resp.data['score']), Decimal('0.00'))
        failed = {c['id'] for c in resp.data['feedback']['criteria'] if not c['passed']}
        self.assertIn('reads_data', failed)

    def test_required_keyword_is_enforced(self):
        resp = self.submit("SELECT d.name, (SELECT COUNT(*) FROM employees e WHERE e.dept_id = d.id) "
                           "FROM departments d")
        self.assertFalse(resp.data['is_correct'])
        self.assertEqual(resp.data['feedback']['keywords_missing'], ['LEFT JOIN'])

    def test_wrong_sort_order_is_not_correct(self):
        resp = self.submit('SELECT name FROM employees ORDER BY salary ASC',
                           exercise=self.exercises[1])
        self.assertFalse(resp.data['is_correct'])
        self.assertEqual(Decimal(resp.data['score']), Decimal('0.00'))
        self.assertTrue(any('порядок' in h for h in resp.data['feedback']['hints']))
        order = next(c for c in resp.data['feedback']['criteria'] if c['id'] == 'order')
        self.assertFalse(order['passed'])

    def test_correct_sort_order_passes(self):
        resp = self.submit(BY_SALARY_DESC, exercise=self.exercises[1])
        self.assertTrue(resp.data['is_correct'])

    def test_sql_error_is_reported(self):
        resp = self.submit('SELEC name FROM employees', exercise=self.exercises[1])
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data['status'], 'error')
        self.assertFalse(resp.data['is_correct'])
        self.assertEqual(Decimal(resp.data['score']), Decimal('0.00'))
        self.assertTrue(resp.data['error_message'])

    def test_literal_with_a_surname_is_not_blocked_by_the_validator(self):
        resp = self.submit("SELECT name FROM employees WHERE name = 'Grant'",
                           exercise=self.exercises[1])
        self.assertEqual(resp.data['status'], 'completed')

    def test_union_is_allowed_for_students(self):
        resp = self.submit("SELECT name FROM employees UNION SELECT name FROM departments",
                           exercise=self.exercises[1])
        self.assertEqual(resp.data['status'], 'completed')

    # ── aggregates and history ──────────────────────────────────────────

    def test_user_result_tracks_best_score_and_completion(self):
        self.submit("SELECT d.name, COUNT(e.id) FROM departments d "
                    "JOIN employees e ON e.dept_id = d.id GROUP BY d.name")
        self.submit(COUNT_PER_DEPT)
        self.submit("SELECT 'x', 1")

        result = UserResult.objects.get(student=self.student, exercise=self.exercises[0])
        self.assertEqual(result.total_attempts, 3)
        self.assertEqual(result.best_score, Decimal('100.00'))
        self.assertTrue(result.is_completed)
        self.assertIsNotNone(result.first_completed_at)

    def test_my_submissions_lists_attempts_in_order(self):
        self.submit(COUNT_PER_DEPT)
        self.submit(BY_SALARY_DESC, exercise=self.exercises[1])
        # Same path the frontend uses (api/lessons.ts getMySubmissions).
        resp = self.client.get(
            f'/api/courses/{self.course_id}/lessons/{self.lesson.id}/submissions/my/')
        self.assertEqual(resp.status_code, 200)
        self.assertIsInstance(resp.data, list)
        self.assertEqual(len(resp.data), 2)
        self.assertEqual({i['attempt_number'] for i in resp.data}, {1})
        self.assertTrue(all('feedback' in i and 'score' in i for i in resp.data))

    def test_lesson_is_completed_after_all_exercises_are_solved(self):
        self.submit(COUNT_PER_DEPT)
        resp = self.client.get(f'/api/courses/{self.course_id}/lessons/{self.lesson.id}/')
        self.assertFalse(resp.data['user_completed'])
        self.submit(BY_SALARY_DESC, exercise=self.exercises[1])
        resp = self.client.get(f'/api/courses/{self.course_id}/lessons/{self.lesson.id}/')
        self.assertTrue(resp.data['user_completed'])

    def test_instructor_sees_student_submissions(self):
        self.submit(COUNT_PER_DEPT)
        self.as_instructor()
        resp = self.client.get(
            f'/api/courses/{self.course_id}/lessons/{self.lesson.id}/submissions/')
        items = resp.data['results'] if 'results' in resp.data else resp.data
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['student'], self.student.id)

    # ── guards ──────────────────────────────────────────────────────────

    def test_attempt_limit_is_enforced(self):
        self.as_instructor()
        lesson = self.create_lesson(title='Контрольна', max_attempts=1)
        exercise = lesson.exercises.first()
        self.as_student()
        first = self.submit("SELECT 'x', 1", exercise=exercise, lesson=lesson)
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        second = self.submit(COUNT_PER_DEPT, exercise=exercise, lesson=lesson)
        self.assertEqual(second.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('attempts', second.data['detail'].lower())

    def test_unenrolled_student_cannot_submit(self):
        self.as_student(self.outsider)
        resp = self.submit(COUNT_PER_DEPT)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_unpublished_lesson_rejects_submissions(self):
        Lesson.objects.filter(id=self.lesson.id).update(is_published=False)
        resp = self.submit(COUNT_PER_DEPT)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_exercise_must_belong_to_the_lesson(self):
        self.as_instructor()
        other = self.create_lesson(title='Інший урок')
        self.as_student()
        resp = self.submit(COUNT_PER_DEPT, exercise=other.exercises.first())
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_no_submission_row_is_left_without_a_grade(self):
        self.submit(COUNT_PER_DEPT)
        self.submit('SELEC x')
        for submission in Submission.objects.all():
            self.assertIsNotNone(submission.score)
            self.assertIsNotNone(submission.graded_at)

    # ── instructor validation of datasets ───────────────────────────────

    def test_validate_exercises_reports_surviving_mutants(self):
        self.as_instructor()
        resp = self.client.post(
            f'/api/courses/{self.course_id}/lessons/{self.lesson.id}/validate-exercises/')
        self.assertEqual(resp.status_code, 200, resp.data)
        by_title = {e['title']: e for e in resp.data['exercises']}

        first = by_title['Кількість працівників у кожному відділі']
        self.assertEqual(first['datasets'], ['основний', 'порожній відділ'])
        self.assertNotIn('join_type', {m['kind'] for m in first['surviving']})

        second = by_title['Прізвища за спаданням зарплати']
        self.assertEqual(second['datasets'], ['основний'])
        self.assertGreater(second['mutants_total'], 0)

    def test_validate_exercises_is_instructor_only(self):
        resp = self.client.post(
            f'/api/courses/{self.course_id}/lessons/{self.lesson.id}/validate-exercises/')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    # ── input validation ────────────────────────────────────────────────

    def create_lesson_raw(self, exercises):
        self.as_instructor()
        return self.client.post(f'/api/courses/{self.course_id}/lessons/', {
            'title': 'Валідація', 'lesson_type': 'practice', 'module_id': self.module_id,
            'exercises': exercises,
        }, format='json')

    def test_check_datasets_must_be_a_list(self):
        resp = self.create_lesson_raw([{'title': 'x', 'check_datasets': 'oops'}])
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_check_dataset_items_need_seed_sql(self):
        resp = self.create_lesson_raw([{'title': 'x', 'check_datasets': [{'name': 'n'}]}])
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_too_many_check_datasets_are_rejected(self):
        items = [{'name': f'd{i}', 'seed_sql': 'SELECT 1'} for i in range(11)]
        resp = self.create_lesson_raw([{'title': 'x', 'check_datasets': items}])
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_check_datasets_are_normalized_on_save(self):
        resp = self.create_lesson_raw([{'title': 'x', 'expected_query': 'SELECT 1',
                                        'check_datasets': [{'seed_sql': 'SELECT 1'}]}])
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        lesson = Lesson.objects.get(course_id=self.course_id, title='Валідація')
        saved = lesson.exercises.first().check_datasets
        self.assertEqual(saved[0]['name'], 'контрольний 1')
        self.assertEqual(saved[0]['targets'], '')

    def test_update_exercise_in_lesson_is_graded_by_execution(self):
        self.as_instructor()
        lesson = self.create_lesson(title='DML', exercises=[{
            'title': 'Підвищити зарплати', 'dataset_id': self.dataset_id,
            'expected_query': 'UPDATE employees SET salary = salary + 100',
        }])
        exercise = lesson.exercises.first()
        self.as_student()
        wrong = self.submit('DELETE FROM employees', exercise=exercise, lesson=lesson)
        self.assertFalse(wrong.data['is_correct'])
        right = self.submit('UPDATE employees SET salary = salary + 100', exercise=exercise,
                            lesson=lesson)
        self.assertTrue(right.data['is_correct'], right.data)
        self.assertEqual(right.data['feedback']['mode'], 'execution')
        self.assertEqual([c['id'] for c in right.data['feedback']['criteria']],
                         ['execution', 'state'])


    def test_instructor_threshold_lets_one_criterion_fail(self):
        self.as_instructor()
        lesson = self.create_lesson('Поріг', exercises=[{
            'title': 'За спаданням', 'expected_query': BY_SALARY_DESC,
            'dataset_id': self.dataset_id,
            'criteria': {'enabled': ['columns', 'complete', 'precise', 'order'], 'threshold': 4},
        }])
        exercise = lesson.exercises.first()
        self.as_student()
        resp = self.submit('SELECT name FROM employees ORDER BY salary', exercise=exercise,
                           lesson=lesson)
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        fb = resp.data['feedback']
        self.assertEqual((fb['passed_count'], fb['total'], fb['threshold']), (4, 5, 4))
        self.assertTrue(resp.data['is_correct'])
        self.assertEqual(Decimal(resp.data['score']), Decimal('100.00'))
        self.assertEqual([c['id'] for c in fb['criteria'] if not c['passed']], ['order'])

    def test_threshold_not_met_scores_zero(self):
        self.as_instructor()
        lesson = self.create_lesson('Поріг 2', exercises=[{
            'title': 'За спаданням', 'expected_query': BY_SALARY_DESC,
            'dataset_id': self.dataset_id,
            'criteria': {'enabled': ['columns', 'complete', 'precise', 'order'], 'threshold': 5},
        }])
        exercise = lesson.exercises.first()
        self.as_student()
        resp = self.submit('SELECT name FROM employees ORDER BY salary', exercise=exercise,
                           lesson=lesson)
        self.assertFalse(resp.data['is_correct'])
        self.assertEqual(Decimal(resp.data['score']), Decimal('0.00'))
        self.assertIn('потрібно 5', resp.data['feedback']['message'])

    def test_lesson_score_is_the_sum_of_exercise_scores(self):
        self.submit(COUNT_PER_DEPT, self.exercises[0])
        self.submit(BY_SALARY_DESC, self.exercises[1])
        resp = self.client.get(f'/api/courses/{self.course_id}/lessons/')
        lessons = resp.data['results'] if isinstance(resp.data, dict) else resp.data
        lesson = next(l for l in lessons if l['id'] == str(self.lesson.id))
        self.assertEqual(Decimal(str(lesson['user_best_score'])), Decimal('200.00'))

    def test_result_with_decimal_and_dates_is_stored(self):
        from unittest import mock
        import datetime as dt
        from grading.service import Execution

        def fake_runner(db_type, timeout, **kw):
            def run(sql, dataset, purpose):
                return Execution(True, ['name', 'salary', 'hired'],
                                 [['Іваненко', Decimal('6000.00'), dt.date(2021, 3, 15)]])
            return run

        with mock.patch('submissions.views.make_runner', fake_runner):
            resp = self.submit('SELECT name, salary, hired FROM employees', self.exercises[1])
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertEqual(resp.data['result']['rows'][0], ['Іваненко', 6000, '2021-03-15'])


class AssignmentGradingTestCase(APITestCase):
    def setUp(self):
        self.instructor = User.objects.create_user(
            email='t@test.com', password='x', role=User.Role.INSTRUCTOR,
            first_name='В', last_name='Т')
        self.student = User.objects.create_user(
            email='s@test.com', password='x', role=User.Role.STUDENT,
            first_name='С', last_name='Т')
        self.client.force_authenticate(self.instructor)
        course = self.client.post('/api/courses/', {
            'title': 'К', 'database_type': 'sqlite', 'is_published': True}, format='json')
        self.course_id = course.data['id']
        dataset = self.client.post(f'/api/courses/{self.course_id}/datasets/', {
            'name': 'D', 'database_type': 'sqlite', 'schema_sql': SCHEMA, 'seed_sql': SEED,
        }, format='json')
        self.dataset_id = dataset.data['id']
        self.client.force_authenticate(self.student)
        code = Course.objects.get(id=self.course_id).course_code
        self.client.post('/api/courses/join/', {'code': code}, format='json')

    def create_assignment(self, **overrides):
        self.client.force_authenticate(self.instructor)
        payload = {
            'title': 'Завдання', 'description': 'опис', 'dataset': self.dataset_id,
            'query_type': 'select', 'expected_query': 'SELECT name FROM employees WHERE salary >= 5000',
            'is_published': True,
            'check_datasets': [{'name': 'межа', 'seed_sql': BOUNDARY_SEED, 'targets': 'рівно 5000'}],
        }
        payload.update(overrides)
        resp = self.client.post(f'/api/courses/{self.course_id}/assignments/', payload,
                                format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.client.force_authenticate(self.student)
        return Assignment.objects.get(course_id=self.course_id, title=payload['title'])

    def submit(self, assignment, query):
        return self.client.post(
            f'/api/courses/{self.course_id}/assignments/{assignment.id}/submissions/',
            {'query': query}, format='json')

    def test_select_assignment_is_graded(self):
        assignment = self.create_assignment()
        ok = self.submit(assignment, 'SELECT name FROM employees WHERE salary >= 5000')
        self.assertTrue(ok.data['is_correct'], ok.data)
        boundary_bug = self.submit(assignment, 'SELECT name FROM employees WHERE salary > 5000')
        self.assertFalse(boundary_bug.data['is_correct'])
        self.assertEqual(boundary_bug.data['feedback']['failed_datasets'][0]['name'], 'межа')

    def test_update_assignment_compares_affected_rows(self):
        assignment = self.create_assignment(
            title='Оновлення', query_type='update',
            expected_query='UPDATE employees SET salary = salary + 100', check_datasets=[])
        same = self.submit(assignment, 'UPDATE employees SET salary = salary + 100')
        self.assertTrue(same.data['is_correct'], same.data)
        self.assertEqual(same.data['feedback']['mode'], 'execution')
        partial = self.submit(assignment, 'UPDATE employees SET salary = salary + 100 WHERE dept_id = 1')
        self.assertFalse(partial.data['is_correct'])

    def test_student_detail_hides_reference_and_hidden_datasets(self):
        assignment = self.create_assignment()
        resp = self.client.get(f'/api/courses/{self.course_id}/assignments/{assignment.id}/')
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('expected_query', resp.data)
        self.assertNotIn('check_datasets', resp.data)
