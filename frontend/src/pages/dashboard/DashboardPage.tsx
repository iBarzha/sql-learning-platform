import { Link } from 'react-router-dom';
import { useAuthStore } from '@/store/authStore';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Spinner } from '@/components/ui/spinner';
import { BookOpen, CheckCircle, Clock, TrendingUp, ArrowRight, Sparkles } from 'lucide-react';
import { useCourses } from '@/hooks/queries/useCourses';
import { useMyProgress } from '@/hooks/queries/useSubmissions';

export function DashboardPage() {
  const { user } = useAuthStore();
  const { data: coursesData, isLoading: coursesLoading } = useCourses({ is_published: true });
  const { data: progress = [], isLoading: progressLoading } = useMyProgress();

  const loading = coursesLoading || progressLoading;
  const courses = coursesData?.results ?? [];

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <Spinner size="lg" />
      </div>
    );
  }

  const enrolledCourses = courses.filter((c) => c.is_enrolled);
  const totalCompleted = progress.reduce((sum, p) => sum + p.completed_assignments, 0);
  const totalAssignments = progress.reduce((sum, p) => sum + p.total_assignments, 0);
  const avgScore = progress.length > 0
    ? Math.round(progress.reduce((sum, p) => sum + p.percentage_score, 0) / progress.length)
    : 0;

  const stats = [
    {
      label: 'Enrolled Courses',
      value: enrolledCourses.length,
      icon: BookOpen,
      color: 'text-primary',
      bg: 'bg-primary/10',
    },
    {
      label: 'Completed',
      value: totalCompleted,
      subtitle: `of ${totalAssignments} lessons`,
      icon: CheckCircle,
      color: 'text-accent',
      bg: 'bg-accent/10',
    },
    {
      label: 'In Progress',
      value: totalAssignments - totalCompleted,
      icon: Clock,
      color: 'text-chart-4',
      bg: 'bg-chart-4/10',
    },
    {
      label: 'Avg. Score',
      value: `${avgScore}%`,
      icon: TrendingUp,
      color: 'text-chart-5',
      bg: 'bg-chart-5/10',
    },
  ];

  return (
    <div className="space-y-8">
      {/* Welcome section */}
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <h1 className="text-3xl font-bold tracking-tight">
            Welcome back, {user?.first_name || 'there'}!
          </h1>
          <Sparkles className="h-6 w-6 text-primary" />
        </div>
        <p className="text-muted-foreground text-lg">
          {user?.role === 'instructor'
            ? 'Manage your courses and track student progress.'
            : 'Continue learning and practicing SQL.'}
        </p>
      </div>

      {/* Stats cards */}
      <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
        {stats.map((stat) => (
          <Card key={stat.label} className="relative overflow-hidden">
            <CardContent className="p-6">
              <div className="flex items-start justify-between">
                <div className="space-y-2">
                  <p className="text-sm font-medium text-muted-foreground">{stat.label}</p>
                  <p className="text-3xl font-bold tracking-tight">{stat.value}</p>
                  {stat.subtitle && (
                    <p className="text-xs text-muted-foreground">{stat.subtitle}</p>
                  )}
                </div>
                <div className={`${stat.bg} p-3 rounded-xl`}>
                  <stat.icon className={`h-5 w-5 ${stat.color}`} />
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Course progress */}
      <Card>
        <CardHeader className="pb-4">
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-xl">Your Courses</CardTitle>
              <CardDescription className="mt-1">Continue where you left off</CardDescription>
            </div>
            {enrolledCourses.length > 0 && (
              <Link
                to="/courses"
                className="text-sm font-medium text-primary hover:text-primary/80 flex items-center gap-1 transition-colors"
              >
                View all <ArrowRight className="h-4 w-4" />
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
              <h3 className="font-semibold text-lg mb-2">No courses yet</h3>
              <p className="text-muted-foreground mb-6 max-w-sm mx-auto">
                Start your SQL learning journey by enrolling in a course.
              </p>
              <Link
                to="/courses"
                className="inline-flex items-center gap-2 px-5 py-2.5 bg-primary text-primary-foreground font-medium rounded-xl shadow-warm hover:shadow-warm-md transition-all"
              >
                Browse courses <ArrowRight className="h-4 w-4" />
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
                          by {course.instructor_name}
                        </p>
                      </div>
                      <div className="text-right shrink-0">
                        <div className="text-sm font-semibold mb-2">{Math.round(percent)}%</div>
                        <div className="w-28 h-2 bg-secondary rounded-full overflow-hidden">
                          <div
                            className="h-full bg-primary rounded-full transition-all duration-500"
                            style={{ width: `${percent}%` }}
                          />
                        </div>
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
