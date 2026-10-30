"""Course progress is counted over every published task, not only the attempted ones."""

from decimal import Decimal

from rest_framework.test import APITestCase

from assignments.models import Assignment
from courses.models import Course, Enrollment, Lesson, LessonExercise, Module
from submissions.models import UserResult
from submissions.progress import course_progress
from users.models import User


class ProgressTests(APITestCase):
    def setUp(self):
        self.instructor = User.objects.create_user(
            email='t@test.com', password='x', role=User.Role.INSTRUCTOR, first_name='T', last_name='T')
        self.other_instructor = User.objects.create_user(
            email='t2@test.com', password='x', role=User.Role.INSTRUCTOR, first_name='O', last_name='T')
        self.student = User.objects.create_user(
            email='s@test.com', password='x', role=User.Role.STUDENT, first_name='S', last_name='S')

        self.course = self._course('Основи SQL', self.instructor)
        module = Module.objects.create(course=self.course, title='M', is_published=True)
        lesson = Lesson.objects.create(course=self.course, module=module, title='Практика',
                                       lesson_type='practice', is_published=True)
        self.exercises = [
            LessonExercise.objects.create(lesson=lesson, order=i, title=f'E{i}',
                                          expected_query='SELECT 1')
            for i in range(20)
        ]
        draft = Lesson.objects.create(course=self.course, module=module, title='Чернетка',
                                      lesson_type='practice', is_published=False)
        draft_exercise = LessonExercise.objects.create(lesson=draft, title='D',
                                                       expected_query='SELECT 1')
        theory = Lesson.objects.create(course=self.course, module=module, title='Теорія',
                                       lesson_type='theory', is_published=True)
        LessonExercise.objects.create(lesson=theory, title='T', expected_query='SELECT 1')
        Assignment.objects.create(course=self.course, title='Чернетка', description='d',
                                  expected_query='SELECT 1', is_published=False)

        UserResult.objects.create(student=self.student, lesson=lesson, exercise=self.exercises[0],
                                  best_score=Decimal('100'), is_completed=True, total_attempts=1)
        # A result on an unpublished lesson must not inflate the numbers.
        UserResult.objects.create(student=self.student, lesson=draft, exercise=draft_exercise,
                                  best_score=Decimal('100'), is_completed=True, total_attempts=1)

        self.empty_course = self._course('Без спроб', self.instructor)
        self._course('Чужий курс', self.other_instructor)
        self._course('Покинутий', self.instructor, status='dropped')

    def _course(self, title, instructor, status='active'):
        course = Course.objects.create(title=title, instructor=instructor,
                                       database_type='sqlite', is_published=True)
        Enrollment.objects.create(student=self.student, course=course, status=status)
        return course

    @staticmethod
    def by_title(data):
        return {entry['course_title']: entry for entry in data}

    def test_one_perfect_exercise_out_of_twenty_is_five_percent(self):
        self.client.force_authenticate(self.student)
        resp = self.client.get('/api/results/my_progress/')
        self.assertEqual(resp.status_code, 200, resp.data)
        entry = self.by_title(resp.data)['Основи SQL']
        self.assertEqual(entry['total_assignments'], 20)        # draft and theory excluded
        self.assertEqual(entry['completed_assignments'], 1)
        self.assertEqual(entry['max_possible_score'], 2000)
        self.assertEqual(entry['total_score'], 100.0)
        self.assertEqual(entry['percentage_score'], 5.0)
        self.assertEqual(entry['completion_rate'], 5.0)
        self.assertEqual(set(entry), {
            'course_id', 'course_title', 'total_assignments', 'completed_assignments',
            'total_score', 'max_possible_score', 'completion_rate', 'percentage_score'})

    def test_published_assignments_count_as_tasks(self):
        assignment = Assignment.objects.create(course=self.course, title='A', description='d',
                                               expected_query='SELECT 1', is_published=True,
                                               max_score=50)
        UserResult.objects.create(student=self.student, assignment=assignment,
                                  best_score=Decimal('25'), total_attempts=1)
        self.client.force_authenticate(self.student)
        entry = self.by_title(self.client.get('/api/results/my_progress/').data)['Основи SQL']
        self.assertEqual(entry['total_assignments'], 21)
        self.assertEqual(entry['max_possible_score'], 2050)
        self.assertEqual(entry['total_score'], 125.0)
        self.assertEqual(entry['completed_assignments'], 1)

    def test_enrolled_course_without_results_shows_zeros(self):
        self.client.force_authenticate(self.student)
        data = self.by_title(self.client.get('/api/results/my_progress/').data)
        self.assertEqual(data['Без спроб'], {
            'course_id': str(self.empty_course.id), 'course_title': 'Без спроб',
            'total_assignments': 0, 'completed_assignments': 0, 'total_score': 0.0,
            'max_possible_score': 0, 'completion_rate': 0, 'percentage_score': 0})
        self.assertIn('Чужий курс', data)
        self.assertNotIn('Покинутий', data)      # only active enrollments

    def test_course_filter_keeps_the_list_shape(self):
        self.client.force_authenticate(self.student)
        resp = self.client.get(f'/api/results/my_progress/?course={self.course.id}')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual([e['course_title'] for e in resp.data], ['Основи SQL'])
        bad = self.client.get('/api/results/my_progress/?course=nope')
        self.assertEqual(bad.status_code, 400)

    def test_student_progress_shows_only_the_instructors_courses(self):
        self.client.force_authenticate(self.instructor)
        resp = self.client.get(f'/api/results/student_progress/?student={self.student.id}')
        self.assertEqual(resp.status_code, 200, resp.data)
        data = self.by_title(resp.data)
        self.assertEqual(set(data), {'Основи SQL', 'Без спроб'})
        self.assertEqual(data['Основи SQL']['percentage_score'], 5.0)

    def test_student_progress_is_instructor_only(self):
        self.client.force_authenticate(self.student)
        resp = self.client.get(f'/api/results/student_progress/?student={self.student.id}')
        self.assertEqual(resp.status_code, 403)

    def test_query_count_does_not_grow_with_courses(self):
        courses = Course.objects.filter(enrollments__student=self.student).distinct()
        with self.assertNumQueries(4):   # courses, assignments, exercises, results
            course_progress(self.student, courses)
