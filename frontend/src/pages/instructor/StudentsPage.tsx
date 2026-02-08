import { useState } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Spinner } from '@/components/ui/spinner';
import { ArrowLeft, Search, Users, Mail, Calendar } from 'lucide-react';
import { useCourse, useCourseEnrollments } from '@/hooks/queries/useCourses';

export function StudentsPage() {
  const { courseId } = useParams<{ courseId: string }>();
  const navigate = useNavigate();

  const { data: course, isLoading: courseLoading } = useCourse(courseId);
  const { data: enrollments = [], isLoading: enrollmentsLoading } = useCourseEnrollments(courseId);
  const loading = courseLoading || enrollmentsLoading;
  const [search, setSearch] = useState('');

  const filteredEnrollments = enrollments.filter(
    (e) =>
      e.student.full_name.toLowerCase().includes(search.toLowerCase()) ||
      e.student.email.toLowerCase().includes(search.toLowerCase())
  );

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
        <Button variant="ghost" size="icon" onClick={() => navigate(-1)}>
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div>
          <h1 className="text-2xl font-bold">Students</h1>
          <p className="text-muted-foreground">{course.title}</p>
        </div>
      </div>

      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          placeholder="Search students..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="pl-9"
        />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Enrolled Students</CardTitle>
          <CardDescription>
            {enrollments.length} students enrolled
          </CardDescription>
        </CardHeader>
        <CardContent>
          {filteredEnrollments.length === 0 ? (
            <div className="text-center py-12">
              <Users className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
              <h3 className="font-medium text-lg mb-2">
                {search ? 'No students found' : 'No students yet'}
              </h3>
              <p className="text-muted-foreground">
                {search
                  ? 'Try adjusting your search'
                  : 'Students will appear here once they enroll'}
              </p>
            </div>
          ) : (
            <div className="space-y-2">
              {filteredEnrollments.map((enrollment) => (
                <div
                  key={enrollment.id}
                  className="flex items-center gap-4 p-4 rounded-lg border"
                >
                  <div className="flex items-center justify-center w-10 h-10 rounded-full bg-primary/10 text-primary font-medium">
                    {enrollment.student.first_name[0]}
                    {enrollment.student.last_name[0]}
                  </div>
                  <div className="flex-1 min-w-0">
                    <h3 className="font-medium">{enrollment.student.full_name}</h3>
                    <div className="flex items-center gap-4 text-sm text-muted-foreground">
                      <span className="flex items-center gap-1">
                        <Mail className="h-3 w-3" />
                        {enrollment.student.email}
                      </span>
                      <span className="flex items-center gap-1">
                        <Calendar className="h-3 w-3" />
                        {new Date(enrollment.enrolled_at).toLocaleDateString()}
                      </span>
                    </div>
                  </div>
                  <Badge
                    variant={
                      enrollment.status === 'active'
                        ? 'default'
                        : enrollment.status === 'completed'
                        ? 'secondary'
                        : 'outline'
                    }
                  >
                    {enrollment.status}
                  </Badge>
                  {enrollment.grade !== null && enrollment.grade !== undefined && (
                    <div className="text-right">
                      <div className="font-medium">{enrollment.grade}%</div>
                      <div className="text-xs text-muted-foreground">Grade</div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
