import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuthStore } from '@/store/authStore';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Spinner } from '@/components/ui/spinner';
import { BookOpen, CheckCircle, Clock, TrendingUp } from 'lucide-react';
import coursesApi from '@/api/courses';
import submissionsApi from '@/api/submissions';
import type { Course, CourseProgress } from '@/types';

export function DashboardPage() {
  const { user } = useAuthStore();
  const [courses, setCourses] = useState<Course[]>([]);
  const [progress, setProgress] = useState<CourseProgress[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadData() {
      try {
        const [coursesRes, progressRes] = await Promise.all([
          coursesApi.list({ is_published: true }),
          submissionsApi.getMyProgress().catch(() => []),
        ]);
        setCourses(coursesRes.results);
        setProgress(progressRes);
      } catch (error) {
        console.error('Failed to load dashboard data:', error);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Spinner size="lg" />
      </div>
    );
  }

  const enrolledCourses = courses.filter((c) => c.is_enrolled);
  const totalCompleted = progress.reduce((sum, p) => sum + p.completed_assignments, 0);
  const totalAssignments = progress.reduce((sum, p) => sum + p.total_assignments, 0);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Welcome back, {user?.first_name}!</h1>
        <p className="text-muted-foreground">
          {user?.role === 'instructor'
            ? 'Manage your courses and track student progress.'
            : 'Continue learning and practicing SQL.'}
        </p>
      </div>

      {/* Stats cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Enrolled Courses</CardTitle>
            <BookOpen className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{enrolledCourses.length}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Completed</CardTitle>
            <CheckCircle className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{totalCompleted}</div>
            <p className="text-xs text-muted-foreground">
              of {totalAssignments} assignments
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">In Progress</CardTitle>
            <Clock className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{totalAssignments - totalCompleted}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Avg. Score</CardTitle>
            <TrendingUp className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {progress.length > 0
                ? Math.round(
                    progress.reduce((sum, p) => sum + p.percentage_score, 0) / progress.length
                  )
                : 0}
              %
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Course progress */}
      <div className="grid gap-4 md:grid-cols-2">
        <Card className="col-span-full">
          <CardHeader>
            <CardTitle>Your Courses</CardTitle>
            <CardDescription>Continue where you left off</CardDescription>
          </CardHeader>
          <CardContent>
            {enrolledCourses.length === 0 ? (
              <div className="text-center py-8">
                <p className="text-muted-foreground mb-4">
                  You haven't enrolled in any courses yet.
                </p>
                <Link
                  to="/courses"
                  className="text-primary hover:underline font-medium"
                >
                  Browse available courses
                </Link>
              </div>
            ) : (
              <div className="space-y-4">
                {enrolledCourses.map((course) => {
                  const courseProgress = progress.find((p) => p.course_id === course.id);
                  const percent = courseProgress?.completion_rate ?? 0;

                  return (
                    <Link
                      key={course.id}
                      to={`/courses/${course.id}`}
                      className="block"
                    >
                      <div className="flex items-center gap-4 p-4 rounded-lg border hover:bg-muted/50 transition-colors">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <h3 className="font-medium truncate">{course.title}</h3>
                            <Badge variant="outline" className="shrink-0">
                              {course.database_type}
                            </Badge>
                          </div>
                          <p className="text-sm text-muted-foreground truncate">
                            {course.instructor_name}
                          </p>
                        </div>
                        <div className="text-right shrink-0">
                          <div className="text-sm font-medium">{Math.round(percent)}%</div>
                          <div className="w-24 h-2 bg-muted rounded-full overflow-hidden">
                            <div
                              className="h-full bg-primary transition-all"
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
    </div>
  );
}
