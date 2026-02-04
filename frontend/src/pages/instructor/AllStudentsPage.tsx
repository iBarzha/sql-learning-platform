import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Spinner } from '@/components/ui/spinner';
import { Search, Users, Mail, BookOpen } from 'lucide-react';
import coursesApi from '@/api/courses';
import type { Course, Enrollment } from '@/types';

interface StudentWithCourses {
  student: Enrollment['student'];
  enrollments: { course: Course; enrollment: Enrollment }[];
}

export function AllStudentsPage() {
  const [courses, setCourses] = useState<Course[]>([]);
  const [allEnrollments, setAllEnrollments] = useState<Enrollment[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');

  useEffect(() => {
    loadData();
  }, []);

  async function loadData() {
    try {
      setLoading(true);
      // First get instructor's courses
      const coursesRes = await coursesApi.list();
      setCourses(coursesRes.results);

      // Then get enrollments for each course
      const enrollmentsPromises = coursesRes.results.map((course) =>
        coursesApi.getEnrollments(course.id).catch(() => [])
      );
      const enrollmentsResults = await Promise.all(enrollmentsPromises);

      // Flatten and add course info
      const allEnrolls: Enrollment[] = [];
      enrollmentsResults.forEach((enrollments, index) => {
        enrollments.forEach((e: Enrollment) => {
          allEnrolls.push({ ...e, course: coursesRes.results[index].id, course_title: coursesRes.results[index].title });
        });
      });
      setAllEnrollments(allEnrolls);
    } catch (err) {
      console.error('Failed to load data:', err);
    } finally {
      setLoading(false);
    }
  }

  // Group enrollments by student
  const studentMap = new Map<string, StudentWithCourses>();
  allEnrollments.forEach((enrollment) => {
    const studentId = enrollment.student.id;
    const course = courses.find((c) => c.id === enrollment.course);
    if (!course) return;

    if (!studentMap.has(studentId)) {
      studentMap.set(studentId, {
        student: enrollment.student,
        enrollments: [],
      });
    }
    studentMap.get(studentId)!.enrollments.push({ course, enrollment });
  });

  const students = Array.from(studentMap.values());
  const filteredStudents = students.filter(
    (s) =>
      s.student.full_name.toLowerCase().includes(search.toLowerCase()) ||
      s.student.email.toLowerCase().includes(search.toLowerCase())
  );

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Spinner size="lg" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Students</h1>
        <p className="text-muted-foreground">
          All students enrolled in your courses
        </p>
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
          <CardTitle>All Students</CardTitle>
          <CardDescription>
            {students.length} students across {courses.length} courses
          </CardDescription>
        </CardHeader>
        <CardContent>
          {filteredStudents.length === 0 ? (
            <div className="text-center py-12">
              <Users className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
              <h3 className="font-medium text-lg mb-2">
                {search ? 'No students found' : 'No students yet'}
              </h3>
              <p className="text-muted-foreground">
                {search
                  ? 'Try adjusting your search'
                  : 'Students will appear here once they enroll in your courses'}
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              {filteredStudents.map((item) => (
                <div
                  key={item.student.id}
                  className="flex items-start gap-4 p-4 rounded-lg border"
                >
                  <div className="flex items-center justify-center w-10 h-10 rounded-full bg-primary/10 text-primary font-medium shrink-0">
                    {item.student.first_name[0]}
                    {item.student.last_name[0]}
                  </div>
                  <div className="flex-1 min-w-0">
                    <h3 className="font-medium">{item.student.full_name}</h3>
                    <div className="flex items-center gap-4 text-sm text-muted-foreground mb-2">
                      <span className="flex items-center gap-1">
                        <Mail className="h-3 w-3" />
                        {item.student.email}
                      </span>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {item.enrollments.map(({ course, enrollment }) => (
                        <Link
                          key={course.id}
                          to={`/courses/${course.id}/students`}
                        >
                          <Badge variant="outline" className="cursor-pointer hover:bg-muted">
                            <BookOpen className="h-3 w-3 mr-1" />
                            {course.title}
                            {enrollment.status !== 'active' && (
                              <span className="ml-1 text-muted-foreground">
                                ({enrollment.status})
                              </span>
                            )}
                          </Badge>
                        </Link>
                      ))}
                    </div>
                  </div>
                  <div className="text-right shrink-0">
                    <div className="text-sm font-medium">
                      {item.enrollments.length} course{item.enrollments.length !== 1 ? 's' : ''}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
