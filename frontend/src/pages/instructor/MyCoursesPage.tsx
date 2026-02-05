import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Spinner } from '@/components/ui/spinner';
import { Plus, Users, BookOpen, Settings, Eye, EyeOff, GraduationCap, Layers } from 'lucide-react';
import coursesApi from '@/api/courses';
import type { Course } from '@/types';

export function MyCoursesPage() {
  const [courses, setCourses] = useState<Course[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadCourses();
  }, []);

  async function loadCourses() {
    try {
      setLoading(true);
      const response = await coursesApi.list();
      setCourses(response.results);
    } catch {
      // Error loading courses - silently fail, UI shows empty state
    } finally {
      setLoading(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <Spinner size="lg" />
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">My Courses</h1>
          <p className="text-muted-foreground mt-1">
            Manage your courses and lessons
          </p>
        </div>
        <Link to="/courses/new">
          <Button className="gap-2">
            <Plus className="h-4 w-4" />
            New Course
          </Button>
        </Link>
      </div>

      {courses.length === 0 ? (
        <Card className="border-dashed">
          <CardContent className="flex flex-col items-center justify-center py-16">
            <div className="h-16 w-16 rounded-2xl bg-primary/10 flex items-center justify-center mb-4">
              <BookOpen className="h-8 w-8 text-primary" />
            </div>
            <h3 className="font-semibold text-lg mb-2">No courses yet</h3>
            <p className="text-muted-foreground text-center mb-6 max-w-sm">
              Create your first course to start teaching students
            </p>
            <Link to="/courses/new">
              <Button className="gap-2">
                <Plus className="h-4 w-4" />
                Create Course
              </Button>
            </Link>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-5 md:grid-cols-2 lg:grid-cols-3">
          {courses.map((course) => (
            <Card key={course.id} className="group transition-all duration-200 hover:shadow-warm-lg hover:border-primary/20">
              <CardHeader className="pb-3">
                <div className="flex items-start justify-between gap-3">
                  <div className="h-11 w-11 rounded-xl bg-primary/10 flex items-center justify-center shrink-0 group-hover:bg-primary/20 transition-colors">
                    <GraduationCap className="h-5 w-5 text-primary" />
                  </div>
                  {course.is_published ? (
                    <Badge className="bg-accent/10 text-accent gap-1">
                      <Eye className="h-3 w-3" />
                      Published
                    </Badge>
                  ) : (
                    <Badge variant="secondary" className="gap-1">
                      <EyeOff className="h-3 w-3" />
                      Draft
                    </Badge>
                  )}
                </div>
                <CardTitle className="text-lg mt-3 line-clamp-1">{course.title}</CardTitle>
                <CardDescription className="line-clamp-2 mt-1">
                  {course.description || 'No description'}
                </CardDescription>
              </CardHeader>
              <CardContent className="pt-0">
                <div className="flex items-center gap-4 text-sm text-muted-foreground mb-4">
                  <div className="flex items-center gap-1.5">
                    <Users className="h-4 w-4" />
                    <span>{course.student_count || 0}</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <Layers className="h-4 w-4" />
                    <span>{course.lesson_count || 0} lessons</span>
                  </div>
                  <Badge variant="outline" className="ml-auto">
                    {course.database_type}
                  </Badge>
                </div>
                <div className="flex gap-2">
                  <Link to={`/courses/${course.id}/manage`} className="flex-1">
                    <Button variant="outline" className="w-full gap-2">
                      <Settings className="h-4 w-4" />
                      Manage
                    </Button>
                  </Link>
                  <Link to={`/courses/${course.id}`}>
                    <Button variant="ghost" size="icon">
                      <Eye className="h-4 w-4" />
                    </Button>
                  </Link>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
