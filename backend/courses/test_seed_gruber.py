"""The Gruber course seed: structure, idempotency, what students receive."""

import io

from django.core.management import call_command
from rest_framework.test import APITestCase

from courses.management.commands.seed_gruber import COURSE_CODE, lessons
from courses.models import Course, Enrollment, LessonExercise
from users.models import User


class SeedGruberTests(APITestCase):
    def setUp(self):
        self.instructor = User.objects.create_user(email='instructor@test.com', password='x',
                                                   role=User.Role.INSTRUCTOR)
        call_command('seed_gruber', stdout=io.StringIO())
        self.course = Course.objects.get(course_code=COURSE_CODE)

    def test_structure_matches_the_book(self):
        plan = lessons()
        self.assertEqual(self.course.database_type, 'postgresql')
        self.assertEqual(self.course.lessons.count(), len(plan))
        self.assertEqual(LessonExercise.objects.filter(lesson__course=self.course).count(),
                         sum(len(exercises) for _, _, exercises in plan))
        self.assertEqual(self.course.modules.count(), 4)
        test = self.course.lessons.get(title='Контрольна робота')
        self.assertEqual(test.time_limit_seconds, 1800)
        self.assertEqual(test.max_attempts, 3)
        self.assertEqual(sum(e.max_score for e in test.exercises.all()), 100)

    def test_every_exercise_has_a_reference_and_a_dataset(self):
        for exercise in LessonExercise.objects.filter(lesson__course=self.course):
            self.assertTrue(exercise.expected_query.strip(), exercise.title)
            self.assertIsNotNone(exercise.dataset, exercise.title)

    def test_seed_is_idempotent(self):
        call_command('seed_gruber', stdout=io.StringIO())
        self.assertEqual(Course.objects.filter(course_code=COURSE_CODE).count(), 1)

    def test_student_sees_criteria_but_not_answers(self):
        student = User.objects.create_user(email='s@test.com', password='x', role=User.Role.STUDENT)
        Enrollment.objects.create(student=student, course=self.course)
        lesson = self.course.lessons.get(title='Підзапити')
        self.client.force_authenticate(student)
        resp = self.client.get(f'/api/courses/{self.course.id}/lessons/{lesson.id}/')
        self.assertEqual(resp.status_code, 200)
        exercise = resp.data['exercises'][0]
        self.assertNotIn('expected_query', exercise)
        self.assertNotIn('check_datasets', exercise)
        ids = [c['id'] for c in exercise['criteria_summary']['criteria']]
        self.assertIn('require:SUBQUERY', ids)
        self.assertIn('forbid:2008', ids)
