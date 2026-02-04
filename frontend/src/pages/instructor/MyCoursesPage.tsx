import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Spinner } from '@/components/ui/spinner';
import { Plus, Users, BookOpen, Settings, Eye, EyeOff } from 'lucide-react';
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
    } catch (error) {
      console.error('Failed to load courses:', error);
    } finally {
      setLoading(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Spinner size="lg" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">My Courses</h1>
          <p className="text-muted-foreground">
            Manage your courses and lessons
          </p>
        </div>
        <Link to="/courses/new">
          <Button>
            <Plus className="h-4 w-4 mr-2" />
            New Course
          </Button>
        </Link>
      </div>

      {courses.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <BookOpen className="h-12 w-12 text-muted-foreground mb-4" />
            <h3 className="font-medium text-lg mb-2">No courses yet</h3>
            <p className="text-muted-foreground text-center mb-4">
              Create your first course to start teaching
            </p>
            <Link to="/courses/new">
              <Button>
                <Plus className="h-4 w-4 mr-2" />
                Create Course
              </Button>
            </Link>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {courses.map((course) => (
            <Card key={course.id} className="hover:shadow-md transition-shadow">
              <CardHeader>
                <div className="flex items-start justify-between gap-2">
                  <CardTitle className="line-clamp-1">{course.title}</CardTitle>
                  {course.is_published ? (
                    <Badge variant="default" className="shrink-0">
                      <Eye className="h-3 w-3 mr-1" />
                      Published
                    </Badge>
                  ) : (
                    <Badge variant="secondary" className="shrink-0">
                      <EyeOff className="h-3 w-3 mr-1" />
                      Draft
                    </Badge>
                  )}
                </div>
                <CardDescription className="line-clamp-2">
                  {course.description || 'No description'}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex items-center justify-between text-sm text-muted-foreground mb-4">
                  <div className="flex items-center gap-1">
                    <Users className="h-4 w-4" />
                    <span>{course.student_count} students</span>
                  </div>
                  <Badge variant="outline">{course.database_type}</Badge>
                </div>
                <div className="flex gap-2">
                  <Link to={`/courses/${course.id}/manage`} className="flex-1">
                    <Button variant="outline" className="w-full">
                      <Settings className="h-4 w-4 mr-2" />
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
