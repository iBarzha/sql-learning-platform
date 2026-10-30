import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuthStore } from '@/store/authStore';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Progress } from '@/components/ui/progress';
import { StatCard } from '@/components/charts/StatCard';
import { BookOpen, CheckCircle, Clock, TrendingUp, ArrowRight, Users, Layers, ClipboardList, Plus } from 'lucide-react';
import { useCourses } from '@/hooks/queries/useCourses';
import { useMyProgress } from '@/hooks/queries/useSubmissions';
import type { Course } from '@/types';

export function DashboardPage() {
  const { t } = useTranslation(['dashboard', 'common']);
  const { user } = useAuthStore();
  const isInstructor = user?.role === 'instructor' || user?.role === 'admin';
  // Instructors see their own courses, drafts included; students only published ones.
  const { data: coursesData, isLoading: coursesLoading } = useCourses(isInstructor ? undefined : { is_published: true });
  const { data: progress = [], isLoading: progressLoading } = useMyProgress();

  const loading = coursesLoading || progressLoading;
  const courses = coursesData?.results ?? [];

  if (loading) {
    return (
      <div className="space-y-8">
        {/* Welcome skeleton */}
        <div className="rounded-2xl bg-gradient-to-r from-primary/10 to-primary/5 p-8">
          <Skeleton className="h-8 w-64 mb-3" />
          <Skeleton className="h-5 w-96" />
        </div>

        {/* Stats skeleton grid */}
        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="rounded-2xl glass shadow-noble-sm p-5">
              <div className="flex items-start justify-between">
                <div className="space-y-3 flex-1">
                  <Skeleton className="h-4 w-24" />
                  <Skeleton className="h-8 w-16" />
                  <Skeleton className="h-3 w-20" />
                </div>
                <Skeleton className="h-10 w-10 rounded-full" />
              </div>
            </div>
          ))}
        </div>

        {/* Course list skeleton */}
        <div className="rounded-2xl glass shadow-noble p-6">
          <Skeleton className="h-6 w-40 mb-2" />
          <Skeleton className="h-4 w-56 mb-6" />
          <div className="space-y-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="flex items-center gap-5 p-5 rounded-xl border border-border/50">
                <Skeleton className="h-12 w-12 rounded-xl shrink-0" />
                <div className="flex-1 space-y-2">
                  <Skeleton className="h-5 w-48" />
                  <Skeleton className="h-4 w-32" />
                </div>
                <Skeleton className="h-2 w-28 rounded-full" />
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (isInstructor) {
    return <InstructorDashboard courses={courses} userId={user?.id} isAdmin={user?.role === 'admin'} />;
  }

  const enrolledCourses = courses.filter((c) => c.is_enrolled);
  const totalCompleted = progress.reduce((sum, p) => sum + p.completed_assignments, 0);
  const totalAssignments = progress.reduce((sum, p) => sum + p.total_assignments, 0);
  const avgScore = progress.length > 0
    ? Math.round(progress.reduce((sum, p) => sum + p.percentage_score, 0) / progress.length)
    : 0;

  const stats = [
    {
      label: t('dashboard:stats.enrolledCourses'),
      value: enrolledCourses.length,
      icon: BookOpen,
      color: 'text-primary',
    },
    {
      label: t('dashboard:stats.completed'),
      value: totalCompleted,
      subtitle: t('dashboard:stats.completedSubtitle', { total: totalAssignments }),
      icon: CheckCircle,
      color: 'text-success',
    },
    {
      label: t('dashboard:stats.inProgress'),
      value: totalAssignments - totalCompleted,
      icon: Clock,
      color: 'text-warning',
    },
    {
      label: t('dashboard:stats.avgScore'),
      value: `${avgScore}%`,
      icon: TrendingUp,
      color: 'text-destructive',
    },
  ];

  return (
    <div className="space-y-8">
      {/* Welcome section */}
      <div className="rounded-2xl bg-gradient-to-r from-primary/10 to-primary/5 p-8">
        <h1 className="text-3xl font-bold tracking-tight mb-2">
            {t('dashboard:welcome.title')}
        </h1>
        <p className="text-muted-foreground text-lg">
          {user?.role === 'instructor'
            ? t('dashboard:welcome.instructorSubtitle')
            : t('dashboard:welcome.studentSubtitle')}
        </p>
      </div>

      {/* Stats cards */}
      <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
        {stats.map((stat) => (
          <StatCard
            key={stat.label}
            label={stat.label}
            value={stat.value}
            subtitle={stat.subtitle}
            icon={stat.icon}
            color={stat.color}
          />
        ))}
      </div>

      {/* Course progress */}
      <Card>
        <CardHeader className="pb-4">
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-xl">{t('dashboard:courses.title')}</CardTitle>
              <CardDescription className="mt-1">{t('dashboard:courses.subtitle')}</CardDescription>
            </div>
            {enrolledCourses.length > 0 && (
              <Link
                to="/courses"
                className="text-sm font-medium text-primary hover:text-primary/80 flex items-center gap-1 transition-colors"
              >
                {t('dashboard:courses.viewAll')} <ArrowRight className="h-4 w-4" />
              </Link>
            )}
          </div>
        </CardHeader>
        <CardContent>
          {enrolledCourses.length === 0 ? (
            <div className="text-center py-12 px-4">
              <div className="mx-auto h-16 w-16 rounded-2xl bg-primary/10 flex items-center justify-center mb-4">
                <BookOpen className="h-8 w-8 text-primary" />
              </div>
              <h3 className="font-semibold text-lg mb-2">{t('dashboard:courses.empty.title')}</h3>
              <p className="text-muted-foreground mb-6 max-w-sm mx-auto">
                {t('dashboard:courses.empty.description')}
              </p>
              <Link
                to="/courses"
                className="inline-flex items-center gap-2 px-5 py-2.5 bg-primary text-primary-foreground font-medium rounded-xl shadow-noble hover:shadow-noble-md transition-all"
              >
                {t('dashboard:courses.empty.browse')} <ArrowRight className="h-4 w-4" />
              </Link>
            </div>
          ) : (
            <div className="space-y-3">
              {enrolledCourses.map((course) => {
                const courseProgress = progress.find((p) => p.course_id === course.id);
                const percent = courseProgress?.completion_rate ?? 0;

                return (
                  <Link
                    key={course.id}
                    to={`/courses/${course.id}`}
                    className="block group"
                  >
                    <div className="flex items-center gap-5 p-5 rounded-xl border border-border/50 bg-card hover:bg-secondary/50 hover:border-primary/20 transition-all duration-200">
                      <div className="h-12 w-12 rounded-xl bg-primary/10 flex items-center justify-center shrink-0 group-hover:bg-primary/20 transition-colors">
                        <BookOpen className="h-6 w-6 text-primary" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <h3 className="font-semibold truncate group-hover:text-primary transition-colors">
                            {course.title}
                          </h3>
                          <Badge variant="secondary" className="shrink-0 text-xs">
                            {course.database_type}
                          </Badge>
                        </div>
                        <p className="text-sm text-muted-foreground truncate">
                          {t('dashboard:courses.byInstructor', { name: course.instructor_name })}
                        </p>
                      </div>
                      <div className="text-right shrink-0 w-32">
                        <div className="text-sm font-semibold mb-2">{Math.round(percent)}%</div>
                        <Progress value={percent} className="h-2" />
                      </div>
                    </div>
                  </Link>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function ownerId(course: Course): string | undefined {
  const owner = course.instructor as unknown;
  if (!owner) return undefined;
  return typeof owner === 'string' ? owner : (owner as { id?: string }).id;
}

function InstructorDashboard({ courses, userId, isAdmin }: { courses: Course[]; userId?: string; isAdmin: boolean }) {
  const { t } = useTranslation(['dashboard', 'common']);
  // The API already scopes the list to what the user may see; an admin oversees every course.
  const mine = isAdmin ? courses : courses.filter((c) => !userId || !ownerId(c) || ownerId(c) === userId);
  const published = mine.filter((c) => c.is_published).length;
  const sum = (pick: (c: Course) => number | undefined) => mine.reduce((acc, c) => acc + (pick(c) ?? 0), 0);

  const stats = [
    {
      label: t('dashboard:instructor.stats.courses'),
      value: mine.length,
      subtitle: t('dashboard:instructor.stats.coursesSubtitle', { count: published }),
      icon: BookOpen,
      color: 'text-primary',
    },
    { label: t('dashboard:instructor.stats.students'), value: sum((c) => c.student_count), icon: Users, color: 'text-success' },
    { label: t('dashboard:instructor.stats.lessons'), value: sum((c) => c.lesson_count), icon: Layers, color: 'text-warning' },
    { label: t('dashboard:instructor.stats.assignments'), value: sum((c) => c.assignment_count), icon: ClipboardList, color: 'text-destructive' },
  ];

  return (
    <div className="space-y-8">
      <div className="rounded-2xl bg-gradient-to-r from-primary/10 to-primary/5 p-8">
        <h1 className="text-3xl font-bold tracking-tight mb-2">{t('dashboard:welcome.title')}</h1>
        <p className="text-muted-foreground text-lg">{t('dashboard:welcome.instructorSubtitle')}</p>
      </div>

      <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
        {stats.map((stat) => (
          <StatCard key={stat.label} label={stat.label} value={stat.value} subtitle={stat.subtitle} icon={stat.icon} color={stat.color} />
        ))}
      </div>

      <Card>
        <CardHeader className="pb-4">
          <div className="flex items-center justify-between gap-4">
            <div>
              <CardTitle className="text-xl">{t('dashboard:instructor.title')}</CardTitle>
              <CardDescription className="mt-1">{t('dashboard:instructor.subtitle')}</CardDescription>
            </div>
            <div className="flex items-center gap-4 shrink-0">
              {mine.length > 0 && (
                <Link to="/my-courses" className="text-sm font-medium text-primary hover:text-primary/80 flex items-center gap-1 transition-colors">
                  {t('dashboard:instructor.all')} <ArrowRight className="h-4 w-4" />
                </Link>
              )}
              <Link
                to="/courses/new"
                className="inline-flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground text-sm font-medium rounded-xl shadow-noble hover:shadow-noble-md transition-all"
              >
                <Plus className="h-4 w-4" /> {t('dashboard:instructor.new')}
              </Link>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {mine.length === 0 ? (
            <div className="text-center py-12 px-4">
              <div className="mx-auto h-16 w-16 rounded-2xl bg-primary/10 flex items-center justify-center mb-4">
                <BookOpen className="h-8 w-8 text-primary" />
              </div>
              <h3 className="font-semibold text-lg mb-2">{t('dashboard:instructor.empty.title')}</h3>
              <p className="text-muted-foreground mb-6 max-w-sm mx-auto">{t('dashboard:instructor.empty.description')}</p>
              <Link
                to="/courses/new"
                className="inline-flex items-center gap-2 px-5 py-2.5 bg-primary text-primary-foreground font-medium rounded-xl shadow-noble hover:shadow-noble-md transition-all"
              >
                {t('dashboard:instructor.empty.create')} <ArrowRight className="h-4 w-4" />
              </Link>
            </div>
          ) : (
            <div className="space-y-3">
              {mine.map((course) => (
                <Link key={course.id} to={`/courses/${course.id}/manage`} className="block group">
                  <div className="flex items-center gap-5 p-5 rounded-xl border border-border/50 bg-card hover:bg-secondary/50 hover:border-primary/20 transition-all duration-200">
                    <div className="h-12 w-12 rounded-xl bg-primary/10 flex items-center justify-center shrink-0 group-hover:bg-primary/20 transition-colors">
                      <BookOpen className="h-6 w-6 text-primary" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <h3 className="font-semibold truncate group-hover:text-primary transition-colors">{course.title}</h3>
                        <Badge variant="secondary" className="shrink-0 text-xs">{course.database_type}</Badge>
                        <Badge variant={course.is_published ? 'default' : 'outline'} className="shrink-0 text-xs">
                          {course.is_published ? t('dashboard:instructor.published') : t('dashboard:instructor.draft')}
                        </Badge>
                      </div>
                      <p className="text-sm text-muted-foreground truncate">
                        {t('dashboard:instructor.students', { count: course.student_count ?? 0 })}
                        {' · '}
                        {t('dashboard:instructor.lessons', { count: course.lesson_count ?? 0 })}
                      </p>
                    </div>
                    <span className="text-sm font-medium text-primary shrink-0 flex items-center gap-1">
                      {t('dashboard:instructor.manage')} <ArrowRight className="h-4 w-4" />
                    </span>
                  </div>
                </Link>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
