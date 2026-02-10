import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { Search, Users, Mail, BookOpen } from 'lucide-react';
import coursesApi from '@/api/courses';
import type { Course, Enrollment } from '@/types';
import { useCourses } from '@/hooks/queries/useCourses';

interface StudentWithCourses {
  student: Enrollment['student'];
  enrollments: { course: Course; enrollment: Enrollment }[];
}

export function AllStudentsPage() {
  const { t } = useTranslation('instructor');
  const { data: coursesData, isLoading: coursesLoading } = useCourses();
  const courses = coursesData?.results ?? [];

  const { data: allEnrollments = [], isLoading: enrollmentsLoading } = useQuery({
    queryKey: ['all-instructor-enrollments', courses.map((c) => c.id)],
    queryFn: async () => {
      const results = await Promise.all(
        courses.map((course) =>
          coursesApi.getEnrollments(course.id).catch(() => [])
        )
      );
      const allEnrolls: Enrollment[] = [];
      results.forEach((enrollments, index) => {
        enrollments.forEach((e: Enrollment) => {
          allEnrolls.push({ ...e, course: courses[index].id, course_title: courses[index].title });
        });
      });
      return allEnrolls;
    },
    enabled: courses.length > 0,
  });

  const loading = coursesLoading || enrollmentsLoading;
  const [search, setSearch] = useState('');

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
      <div className="space-y-6">
        <div className="space-y-2">
          <Skeleton className="h-8 w-32" />
          <Skeleton className="h-4 w-64" />
        </div>
        <Skeleton className="h-10 w-full rounded-xl" />
        <Skeleton className="h-96 w-full rounded-2xl" />
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fade-in">
      <div>
        <h1 className="text-3xl font-bold">{t('students.allStudentsTitle')}</h1>
        <p className="text-muted-foreground">
          {t('students.allStudentsSubtitle')}
        </p>
      </div>

      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          placeholder={t('students.searchPlaceholder')}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="pl-9"
        />
      </div>

      <Card variant="glass">
        <CardHeader>
          <CardTitle>{t('students.allStudents')}</CardTitle>
          <CardDescription>
            {t('students.studentsAcrossCourses', {
              studentCount: students.length,
              courseCount: courses.length,
            })}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {filteredStudents.length === 0 ? (
            <div className="text-center py-12">
              <Users className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
              <h3 className="font-medium text-lg mb-2">
                {search ? t('students.noStudents') : t('students.noStudentsYet')}
              </h3>
              <p className="text-muted-foreground">
                {search ? t('students.noStudentsSearch') : t('students.noStudentsEnrolled')}
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              {filteredStudents.map((item) => (
                <div
                  key={item.student.id}
                  className="flex items-start gap-4 p-4 rounded-xl border border-border/50 hover:bg-muted/30 transition-colors"
                >
                  <Avatar>
                    <AvatarFallback>
                      {item.student.first_name[0]}
                      {item.student.last_name[0]}
                    </AvatarFallback>
                  </Avatar>
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
                      {item.enrollments.length} {item.enrollments.length === 1 ? 'course' : 'courses'}
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
