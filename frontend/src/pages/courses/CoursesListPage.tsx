import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuthStore } from '@/store/authStore';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Spinner } from '@/components/ui/spinner';
import { Plus, Search, Users, BookOpen } from 'lucide-react';
import coursesApi from '@/api/courses';
import type { Course } from '@/types';

export function CoursesListPage() {
  const { user } = useAuthStore();
  const [courses, setCourses] = useState<Course[]>([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadCourses();
  }, []);

  async function loadCourses() {
    try {
      setLoading(true);
      const response = await coursesApi.list({ is_published: true });
      setCourses(response.results);
    } catch (error) {
      console.error('Failed to load courses:', error);
    } finally {
      setLoading(false);
    }
  }

  const filteredCourses = courses.filter(
    (course) =>
      course.title.toLowerCase().includes(search.toLowerCase()) ||
      course.description.toLowerCase().includes(search.toLowerCase())
  );

  const isInstructor = user?.role === 'instructor' || user?.role === 'admin';

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Courses</h1>
          <p className="text-muted-foreground">
            Browse and enroll in available courses
          </p>
        </div>
        {isInstructor && (
          <Link to="/courses/new">
            <Button>
              <Plus className="h-4 w-4 mr-2" />
              Create Course
            </Button>
          </Link>
        )}
      </div>

      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          placeholder="Search courses..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="pl-9"
        />
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-12">
          <Spinner size="lg" />
        </div>
      ) : filteredCourses.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <BookOpen className="h-12 w-12 text-muted-foreground mb-4" />
            <h3 className="font-medium text-lg mb-2">No courses found</h3>
            <p className="text-muted-foreground text-center">
              {search
                ? 'Try adjusting your search terms'
                : 'No courses are available at the moment'}
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {filteredCourses.map((course) => (
            <Link key={course.id} to={`/courses/${course.id}`}>
              <Card className="h-full hover:shadow-md transition-shadow">
                <CardHeader>
                  <div className="flex items-start justify-between gap-2">
                    <CardTitle className="line-clamp-2">{course.title}</CardTitle>
                    <Badge variant="outline" className="shrink-0">
                      {course.database_type}
                    </Badge>
                  </div>
                  <CardDescription className="line-clamp-2">
                    {course.description}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="flex items-center justify-between text-sm text-muted-foreground">
                    <span>{course.instructor_name}</span>
                    <div className="flex items-center gap-1">
                      <Users className="h-4 w-4" />
                      <span>{course.student_count}</span>
                    </div>
                  </div>
                  <div className="flex items-center justify-between mt-2">
                    <span className="text-sm">
                      {course.assignment_count} assignments
                    </span>
                    {course.is_enrolled && (
                      <Badge variant="secondary">Enrolled</Badge>
                    )}
                  </div>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
