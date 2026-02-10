import { useState } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuthStore } from '@/store/authStore';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Spinner } from '@/components/ui/spinner';
import { Progress } from '@/components/ui/progress';
import {
  Dialog,
  DialogTrigger,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
  DialogClose,
} from '@/components/ui/dialog';
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
  const { t } = useTranslation('courses');
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
              ? t('detail.theory')
              : lesson.lesson_type === 'practice'
              ? t('detail.practice')
              : t('detail.mixed')}
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
          <CheckCircle className="h-5 w-5 text-success" />
        ) : hasPractice && lesson.user_best_score != null ? (
          <Clock className="h-5 w-5 text-warning" />
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
  const { t } = useTranslation('courses');

  // No modules -- flat list
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
              {t('detail.otherLessons')}
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
  const { t } = useTranslation('courses');
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
      setError(getApiErrorMessage(err, t('detail.failedEnroll')));
    } finally {
      setEnrolling(false);
    }
  }

  async function handleUnenroll() {
    if (!courseId) return;

    try {
      await unenrollMutation.mutateAsync();
    } catch (err) {
      setError(getApiErrorMessage(err, t('detail.failedUnenroll')));
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
        <h2 className="text-xl font-semibold mb-2">{t('detail.notFound')}</h2>
        <Link to="/courses" className="text-primary hover:underline">
          {t('detail.backToCourses')}
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
    <div className="space-y-6 animate-fade-in">
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
              {t('detail.manage')}
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
              <CardTitle>{t('detail.aboutCourse')}</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="whitespace-pre-wrap">{course.description}</p>
            </CardContent>
          </Card>

          {/* Lessons list */}
          <Card>
            <CardHeader>
              <CardTitle>{t('detail.lessons')}</CardTitle>
              <CardDescription>
                {t('detail.lessonCount', { count: lessons.length })}
              </CardDescription>
            </CardHeader>
            <CardContent>
              {!course.is_enrolled && !canManage ? (
                <div className="text-center py-8">
                  <Lock className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
                  <p className="text-muted-foreground">
                    {t('detail.enrollToAccess')}
                  </p>
                </div>
              ) : lessons.length === 0 ? (
                <p className="text-center py-8 text-muted-foreground">
                  {t('detail.noLessons')}
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
              <CardTitle>{t('detail.courseInfo')}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">{t('detail.students')}</span>
                <div className="flex items-center gap-1">
                  <Users className="h-4 w-4" />
                  <span>{course.student_count}</span>
                </div>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">{t('detail.lessons')}</span>
                <span>{lessons.length}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">{t('detail.database')}</span>
                <Badge variant="outline">{course.database_type}</Badge>
              </div>
              {course.start_date && (
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">{t('detail.startDate')}</span>
                  <span>{new Date(course.start_date).toLocaleDateString()}</span>
                </div>
              )}
              {course.end_date && (
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">{t('detail.endDate')}</span>
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
                  {course.is_enrolled ? t('detail.yourProgress') : t('detail.enroll')}
                </CardTitle>
              </CardHeader>
              <CardContent>
                {course.is_enrolled ? (
                  <div className="space-y-4">
                    <div>
                      <div className="flex items-center justify-between text-sm mb-1">
                        <span>{t('detail.progress')}</span>
                        <span>{Math.round(progressPercent)}%</span>
                      </div>
                      <Progress value={progressPercent} />
                    </div>
                    <p className="text-sm text-muted-foreground">
                      {t('detail.completedOf', { completed: completedCount, total: practiceCount })}
                    </p>
                    <Dialog>
                      <DialogTrigger asChild>
                        <Button variant="outline" className="w-full">
                          {t('detail.unenroll')}
                        </Button>
                      </DialogTrigger>
                      <DialogContent>
                        <DialogHeader>
                          <DialogTitle>{t('detail.unenrollConfirmTitle')}</DialogTitle>
                          <DialogDescription>
                            {t('detail.unenrollConfirmDescription')}
                          </DialogDescription>
                        </DialogHeader>
                        <DialogFooter>
                          <DialogClose asChild>
                            <Button variant="outline">{t('detail.cancel')}</Button>
                          </DialogClose>
                          <DialogClose asChild>
                            <Button variant="destructive" onClick={handleUnenroll}>
                              {t('detail.unenroll')}
                            </Button>
                          </DialogClose>
                        </DialogFooter>
                      </DialogContent>
                    </Dialog>
                  </div>
                ) : (
                  <div className="space-y-4">
                    {course.enrollment_key !== undefined && (
                      <Input
                        placeholder={t('detail.enrollmentKeyPlaceholder')}
                        value={enrollmentKey}
                        onChange={(e) => setEnrollmentKey(e.target.value)}
                      />
                    )}
                    <Button
                      className="w-full"
                      onClick={handleEnroll}
                      disabled={enrolling}
                    >
                      {enrolling ? <Spinner size="sm" /> : t('detail.enrollNow')}
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
