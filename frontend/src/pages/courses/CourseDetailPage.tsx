import { useState } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { useAuthStore } from '@/store/authStore';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Spinner } from '@/components/ui/spinner';
import {
  ArrowLeft,
  CheckCircle,
  Clock,
  Lock,
  Play,
  Settings,
  Users,
  BookOpen,
  Code,
  Layers,
} from 'lucide-react';
import type { Lesson } from '@/api/lessons';
import type { Module } from '@/api/modules';
import { getApiErrorMessage } from '@/lib/utils';
import { useCourse, useEnrollCourse, useUnenrollCourse } from '@/hooks/queries/useCourses';
import { useLessons } from '@/hooks/queries/useLessons';
import { useModules } from '@/hooks/queries/useModules';

const LESSON_TYPE_ICONS = {
  theory: BookOpen,
  practice: Code,
  mixed: Layers,
};

function LessonRow({ lesson, index, courseId }: { lesson: Lesson; index: number; courseId: string }) {
  const TypeIcon = LESSON_TYPE_ICONS[lesson.lesson_type];
  const hasPractice = lesson.lesson_type === 'practice' || lesson.lesson_type === 'mixed';

  return (
    <Link
      to={`/courses/${courseId}/lessons/${lesson.id}`}
      className="flex items-center gap-4 p-4 rounded-lg border hover:bg-muted/50 transition-colors"
    >
      <div className="flex items-center justify-center w-8 h-8 rounded-full bg-muted text-sm font-medium">
        {index + 1}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <h3 className="font-medium truncate">{lesson.title}</h3>
          <Badge variant="outline">
            <TypeIcon className="h-3 w-3 mr-1" />
            {lesson.lesson_type === 'theory'
              ? 'Theory'
              : lesson.lesson_type === 'practice'
              ? 'Practice'
              : 'Mixed'}
          </Badge>
        </div>
        {lesson.description && (
          <p className="text-sm text-muted-foreground truncate">
            {lesson.description}
          </p>
        )}
      </div>
      <div className="shrink-0">
        {hasPractice && lesson.user_completed ? (
          <CheckCircle className="h-5 w-5 text-green-500" />
        ) : hasPractice && lesson.user_best_score !== null ? (
          <Clock className="h-5 w-5 text-yellow-500" />
        ) : (
          <Play className="h-5 w-5 text-muted-foreground" />
        )}
      </div>
    </Link>
  );
}

function LessonsList({
  lessons,
  modules,
  courseId,
}: {
  lessons: Lesson[];
  modules: Module[];
  courseId: string;
}) {
  // No modules — flat list
  if (modules.length === 0) {
    return (
      <div className="space-y-2">
        {lessons.map((lesson, index) => (
          <LessonRow key={lesson.id} lesson={lesson} index={index} courseId={courseId} />
        ))}
      </div>
    );
  }

  // Group lessons by module
  const lessonsByModule = new Map<string | null, Lesson[]>();
  for (const lesson of lessons) {
    const key = lesson.module ?? null;
    if (!lessonsByModule.has(key)) {
      lessonsByModule.set(key, []);
    }
    lessonsByModule.get(key)!.push(lesson);
  }

  const sortedModules = [...modules].sort((a, b) => a.order - b.order);
  const uncategorized = lessonsByModule.get(null) ?? [];
  let globalIndex = 0;

  return (
    <div className="space-y-6">
      {sortedModules.map((mod) => {
        const modLessons = lessonsByModule.get(mod.id) ?? [];
        if (modLessons.length === 0) return null;
        return (
          <div key={mod.id}>
            <h3 className="font-semibold text-sm text-muted-foreground uppercase tracking-wider mb-2">
              {mod.title}
            </h3>
            {mod.description && (
              <p className="text-sm text-muted-foreground mb-3">{mod.description}</p>
            )}
            <div className="space-y-2">
              {modLessons.map((lesson) => {
                globalIndex++;
                return (
                  <LessonRow
                    key={lesson.id}
                    lesson={lesson}
                    index={globalIndex}
                    courseId={courseId}
                  />
                );
              })}
            </div>
          </div>
        );
      })}
      {uncategorized.length > 0 && (
        <div>
          {sortedModules.length > 0 && (
            <h3 className="font-semibold text-sm text-muted-foreground uppercase tracking-wider mb-2">
              Other Lessons
            </h3>
          )}
          <div className="space-y-2">
            {uncategorized.map((lesson) => {
              globalIndex++;
              return (
                <LessonRow
                  key={lesson.id}
                  lesson={lesson}
                  index={globalIndex}
                  courseId={courseId}
                />
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

export function CourseDetailPage() {
  const { courseId } = useParams<{ courseId: string }>();
  const navigate = useNavigate();
  const { user } = useAuthStore();

  const { data: course, isLoading: courseLoading } = useCourse(courseId);
  const { data: lessonsData, isLoading: lessonsLoading } = useLessons(courseId);
  const { data: modules = [], isLoading: modulesLoading } = useModules(courseId);
  const lessons = lessonsData?.results ?? [];
  const loading = courseLoading || lessonsLoading || modulesLoading;

  const [enrolling, setEnrolling] = useState(false);
  const [enrollmentKey, setEnrollmentKey] = useState('');
  const [error, setError] = useState('');

  const enrollMutation = useEnrollCourse(courseId!);
  const unenrollMutation = useUnenrollCourse(courseId!);

  const isInstructor = course?.instructor?.id === user?.id;
  const isAdmin = user?.role === 'admin';
  const canManage = isInstructor || isAdmin;

  async function handleEnroll() {
    if (!courseId) return;

    try {
      setEnrolling(true);
      setError('');
      await enrollMutation.mutateAsync(enrollmentKey || undefined);
    } catch (err) {
      setError(getApiErrorMessage(err, 'Failed to enroll'));
    } finally {
      setEnrolling(false);
    }
  }

  async function handleUnenroll() {
    if (!courseId || !confirm('Are you sure you want to unenroll from this course?')) return;

    try {
      await unenrollMutation.mutateAsync();
    } catch (err) {
      setError(getApiErrorMessage(err, 'Failed to unenroll'));
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
        <Link to="/courses" className="text-primary hover:underline">
          Back to courses
        </Link>
      </div>
    );
  }

  const completedCount = lessons.filter((l) => l.user_completed).length;
  const practiceCount = lessons.filter(
    (l) => l.lesson_type === 'practice' || l.lesson_type === 'mixed'
  ).length;
  const progressPercent = practiceCount > 0 ? (completedCount / practiceCount) * 100 : 0;

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" onClick={() => navigate(-1)}>
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <h1 className="text-3xl font-bold">{course.title}</h1>
            <Badge variant="outline">{course.database_type}</Badge>
          </div>
          <p className="text-muted-foreground">{course.instructor_name}</p>
        </div>
        {canManage && (
          <Link to={`/courses/${courseId}/manage`}>
            <Button variant="outline">
              <Settings className="h-4 w-4 mr-2" />
              Manage
            </Button>
          </Link>
        )}
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <div className="grid gap-6 md:grid-cols-3">
        <div className="md:col-span-2 space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>About this course</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="whitespace-pre-wrap">{course.description}</p>
            </CardContent>
          </Card>

          {/* Lessons list */}
          <Card>
            <CardHeader>
              <CardTitle>Lessons</CardTitle>
              <CardDescription>
                {lessons.length} lessons in this course
              </CardDescription>
            </CardHeader>
            <CardContent>
              {!course.is_enrolled && !canManage ? (
                <div className="text-center py-8">
                  <Lock className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
                  <p className="text-muted-foreground">
                    Enroll in this course to access lessons
                  </p>
                </div>
              ) : lessons.length === 0 ? (
                <p className="text-center py-8 text-muted-foreground">
                  No lessons yet
                </p>
              ) : (
                <LessonsList
                  lessons={lessons}
                  modules={modules}
                  courseId={courseId!}
                />
              )}
            </CardContent>
          </Card>
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Course Info</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">Students</span>
                <div className="flex items-center gap-1">
                  <Users className="h-4 w-4" />
                  <span>{course.student_count}</span>
                </div>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">Lessons</span>
                <span>{lessons.length}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">Database</span>
                <Badge variant="outline">{course.database_type}</Badge>
              </div>
              {course.start_date && (
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Start Date</span>
                  <span>{new Date(course.start_date).toLocaleDateString()}</span>
                </div>
              )}
              {course.end_date && (
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">End Date</span>
                  <span>{new Date(course.end_date).toLocaleDateString()}</span>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Enrollment card */}
          {!canManage && (
            <Card>
              <CardHeader>
                <CardTitle>
                  {course.is_enrolled ? 'Your Progress' : 'Enroll'}
                </CardTitle>
              </CardHeader>
              <CardContent>
                {course.is_enrolled ? (
                  <div className="space-y-4">
                    <div>
                      <div className="flex items-center justify-between text-sm mb-1">
                        <span>Progress</span>
                        <span>{Math.round(progressPercent)}%</span>
                      </div>
                      <div className="h-2 bg-muted rounded-full overflow-hidden">
                        <div
                          className="h-full bg-primary transition-all"
                          style={{ width: `${progressPercent}%` }}
                        />
                      </div>
                    </div>
                    <p className="text-sm text-muted-foreground">
                      {completedCount} of {practiceCount} practice lessons completed
                    </p>
                    <Button
                      variant="outline"
                      className="w-full"
                      onClick={handleUnenroll}
                    >
                      Unenroll
                    </Button>
                  </div>
                ) : (
                  <div className="space-y-4">
                    {course.enrollment_key !== undefined && (
                      <Input
                        placeholder="Enrollment key (if required)"
                        value={enrollmentKey}
                        onChange={(e) => setEnrollmentKey(e.target.value)}
                      />
                    )}
                    <Button
                      className="w-full"
                      onClick={handleEnroll}
                      disabled={enrolling}
                    >
                      {enrolling ? <Spinner size="sm" /> : 'Enroll Now'}
                    </Button>
                  </div>
                )}
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
