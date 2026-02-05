import { useEffect, useState } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Spinner } from '@/components/ui/spinner';
import {
  ArrowLeft,
  Plus,
  Settings,
  Eye,
  EyeOff,
  Trash2,
  GripVertical,
  BookOpen,
  Code,
  Layers,
  Edit,
  Users,
} from 'lucide-react';
import coursesApi from '@/api/courses';
import lessonsApi, { type Lesson } from '@/api/lessons';
import type { Course } from '@/types';

const LESSON_TYPE_ICONS = {
  theory: BookOpen,
  practice: Code,
  mixed: Layers,
};

const LESSON_TYPE_LABELS = {
  theory: 'Theory',
  practice: 'Practice',
  mixed: 'Mixed',
};

export function CourseManagePage() {
  const { courseId } = useParams<{ courseId: string }>();
  const navigate = useNavigate();

  const [course, setCourse] = useState<Course | null>(null);
  const [lessons, setLessons] = useState<Lesson[]>([]);
  const [loading, setLoading] = useState(true);
  const [publishing, setPublishing] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (courseId) {
      loadData();
    }
  }, [courseId]);

  async function loadData() {
    try {
      setLoading(true);
      const [courseData, lessonsData] = await Promise.all([
        coursesApi.get(courseId!),
        lessonsApi.list(courseId!),
      ]);
      setCourse(courseData);
      setLessons(lessonsData.results || []);
    } catch (err) {
      setError('Failed to load course data');
    } finally {
      setLoading(false);
    }
  }

  async function togglePublish() {
    if (!course) return;
    try {
      setPublishing(true);
      await coursesApi.update(courseId!, { is_published: !course.is_published });
      setCourse({ ...course, is_published: !course.is_published });
    } catch (err) {
      setError('Failed to update course');
    } finally {
      setPublishing(false);
    }
  }

  async function toggleLessonPublish(lesson: Lesson) {
    try {
      await lessonsApi.update(courseId!, lesson.id, { is_published: !lesson.is_published });
      setLessons(lessons.map(l =>
        l.id === lesson.id ? { ...l, is_published: !l.is_published } : l
      ));
    } catch (err) {
      setError('Failed to update lesson');
    }
  }

  async function deleteLesson(lessonId: string) {
    if (!confirm('Are you sure you want to delete this lesson?')) return;
    try {
      await lessonsApi.delete(courseId!, lessonId);
      setLessons(lessons.filter(l => l.id !== lessonId));
    } catch (err) {
      setError('Failed to delete lesson');
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Spinner size="lg" />
      </div>
    );
  }

  if (!course) {
    return (
      <div className="text-center py-12">
        <h2 className="text-xl font-semibold mb-2">Course not found</h2>
        <Link to="/my-courses" className="text-primary hover:underline">
          Back to my courses
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" onClick={() => navigate('/my-courses')}>
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold">{course.title}</h1>
            {course.is_published ? (
              <Badge variant="default">Published</Badge>
            ) : (
              <Badge variant="secondary">Draft</Badge>
            )}
          </div>
          <p className="text-muted-foreground">Manage course content and settings</p>
        </div>
        <div className="flex gap-2">
          <Link to={`/courses/${courseId}/students`}>
            <Button variant="outline">
              <Users className="h-4 w-4 mr-2" />
              Students ({course.student_count})
            </Button>
          </Link>
          <Link to={`/courses/${courseId}/edit`}>
            <Button variant="outline">
              <Settings className="h-4 w-4 mr-2" />
              Settings
            </Button>
          </Link>
          <Button onClick={togglePublish} disabled={publishing}>
            {publishing ? (
              <Spinner size="sm" className="mr-2" />
            ) : course.is_published ? (
              <EyeOff className="h-4 w-4 mr-2" />
            ) : (
              <Eye className="h-4 w-4 mr-2" />
            )}
            {course.is_published ? 'Unpublish' : 'Publish'}
          </Button>
        </div>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Lessons</CardTitle>
              <CardDescription>
                {lessons.length} lessons in this course
              </CardDescription>
            </div>
            <Link to={`/courses/${courseId}/lessons/new`}>
              <Button>
                <Plus className="h-4 w-4 mr-2" />
                Add Lesson
              </Button>
            </Link>
          </div>
        </CardHeader>
        <CardContent>
          {lessons.length === 0 ? (
            <div className="text-center py-12">
              <Layers className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
              <h3 className="font-medium text-lg mb-2">No lessons yet</h3>
              <p className="text-muted-foreground mb-4">
                Start building your course by adding lessons
              </p>
              <Link to={`/courses/${courseId}/lessons/new`}>
                <Button>
                  <Plus className="h-4 w-4 mr-2" />
                  Add First Lesson
                </Button>
              </Link>
            </div>
          ) : (
            <div className="space-y-2">
              {lessons.map((lesson, index) => {
                const TypeIcon = LESSON_TYPE_ICONS[lesson.lesson_type];
                return (
                  <div
                    key={lesson.id}
                    className="flex items-center gap-4 p-4 rounded-lg border bg-card hover:bg-muted/50 transition-colors"
                  >
                    <div className="text-muted-foreground cursor-move">
                      <GripVertical className="h-5 w-5" />
                    </div>
                    <div className="flex items-center justify-center w-8 h-8 rounded-full bg-muted text-sm font-medium">
                      {index + 1}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <h3 className="font-medium truncate">{lesson.title}</h3>
                        <Badge variant="outline" className="shrink-0">
                          <TypeIcon className="h-3 w-3 mr-1" />
                          {LESSON_TYPE_LABELS[lesson.lesson_type]}
                        </Badge>
                        {!lesson.is_published && (
                          <Badge variant="secondary" className="shrink-0">
                            Draft
                          </Badge>
                        )}
                      </div>
                      {lesson.description && (
                        <p className="text-sm text-muted-foreground truncate">
                          {lesson.description}
                        </p>
                      )}
                    </div>
                    <div className="flex items-center gap-1">
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => toggleLessonPublish(lesson)}
                        title={lesson.is_published ? 'Unpublish' : 'Publish'}
                      >
                        {lesson.is_published ? (
                          <Eye className="h-4 w-4" />
                        ) : (
                          <EyeOff className="h-4 w-4" />
                        )}
                      </Button>
                      <Link to={`/courses/${courseId}/lessons/${lesson.id}/edit`}>
                        <Button variant="ghost" size="icon" title="Edit">
                          <Edit className="h-4 w-4" />
                        </Button>
                      </Link>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => deleteLesson(lesson.id)}
                        title="Delete"
                        className="text-destructive hover:text-destructive"
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
