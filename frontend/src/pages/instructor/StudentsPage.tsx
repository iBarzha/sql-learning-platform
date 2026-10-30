import { useState } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { Spinner } from '@/components/ui/spinner';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { ArrowLeft, Search, Users, Mail, Calendar, ChevronDown, ChevronUp, Timer, ClipboardList } from 'lucide-react';
import { useCourse, useCourseEnrollments, useStudentTimers } from '@/hooks/queries/useCourses';
import { useStudentProgress } from '@/hooks/queries/useSubmissions';
import { StudentTimersDialog } from '@/components/instructor/StudentTimersDialog';
import { StudentResultsDialog } from '@/components/instructor/StudentResultsDialog';
import type { CourseProgress, User } from '@/types';

function StudentGrades({ studentId }: { studentId: string }) {
  const { t } = useTranslation('instructor');
  const { data: progress, isLoading } = useStudentProgress(studentId);

  if (isLoading) {
    return (
      <div className="flex justify-center py-4">
        <Spinner size="sm" />
      </div>
    );
  }

  if (!progress || progress.length === 0) {
    return (
      <p className="text-sm text-muted-foreground py-2 px-4">
        {t('students.noProgress')}
      </p>
    );
  }

  return (
    <div className="space-y-2">
      {progress.map((cp: CourseProgress) => (
        <div
          key={cp.course_id}
          className="flex items-center gap-4 p-3 rounded-lg bg-muted/30"
        >
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium">{cp.course_title}</p>
            <p className="text-xs text-muted-foreground">
              {t('students.tasks', {
                completed: cp.completed_assignments,
                total: cp.total_assignments,
              })}
            </p>
          </div>
          <div className="flex items-center gap-3">
            <div className="w-24 h-2 rounded-full bg-muted overflow-hidden">
              <div
                className="h-full rounded-full bg-primary transition-all duration-300"
                style={{ width: `${Math.min(cp.completion_rate, 100)}%` }}
              />
            </div>
            <Badge variant="outline" className="min-w-[3rem] justify-center">
              {Math.round(cp.percentage_score)}%
            </Badge>
          </div>
        </div>
      ))}
    </div>
  );
}

/** Per-student instructor tools: task results with manual scores, and timed-lesson clocks. */
function StudentTools({ courseId, student }: { courseId: string; student: User }) {
  const { t } = useTranslation('instructor');
  const { data: timers = [] } = useStudentTimers(courseId, student.id);
  const [showResults, setShowResults] = useState(false);
  const [showTimers, setShowTimers] = useState(false);

  return (
    <div className="flex flex-wrap gap-2">
      <Button variant="outline" size="sm" onClick={() => setShowResults(true)}>
        <ClipboardList className="h-4 w-4 mr-2" />
        {t('students.results.open')}
      </Button>
      {timers.length > 0 && (
        <Button variant="outline" size="sm" onClick={() => setShowTimers(true)}>
          <Timer className="h-4 w-4 mr-2" />
          {t('students.timers.open')}
        </Button>
      )}
      <StudentResultsDialog
        courseId={courseId}
        studentId={student.id}
        studentName={student.full_name}
        open={showResults}
        onOpenChange={setShowResults}
      />
      {timers.length > 0 && (
        <StudentTimersDialog
          courseId={courseId}
          studentId={student.id}
          studentName={student.full_name}
          open={showTimers}
          onOpenChange={setShowTimers}
        />
      )}
    </div>
  );
}

export function StudentsPage() {
  const { t } = useTranslation('instructor');
  const { courseId } = useParams<{ courseId: string }>();
  const navigate = useNavigate();

  const { data: course, isLoading: courseLoading } = useCourse(courseId);
  const { data: enrollments = [], isLoading: enrollmentsLoading } = useCourseEnrollments(courseId);
  const loading = courseLoading || enrollmentsLoading;
  const [search, setSearch] = useState('');
  const [expandedStudentId, setExpandedStudentId] = useState<string | null>(null);

  const filteredEnrollments = enrollments.filter(
    (e) =>
      e.student.full_name.toLowerCase().includes(search.toLowerCase()) ||
      e.student.email.toLowerCase().includes(search.toLowerCase())
  );

  function toggleExpand(studentId: string) {
    setExpandedStudentId((prev) => (prev === studentId ? null : studentId));
  }

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <Skeleton className="h-10 w-10 rounded-full" />
          <div className="space-y-2">
            <Skeleton className="h-6 w-32" />
            <Skeleton className="h-4 w-48" />
          </div>
        </div>
        <Skeleton className="h-10 w-full rounded-xl" />
        <Skeleton className="h-64 w-full rounded-2xl" />
      </div>
    );
  }

  if (!course) {
    return (
      <div className="text-center py-12">
        <h2 className="text-xl font-semibold mb-2">{t('students.courseNotFound')}</h2>
        <Link to="/my-courses" className="text-primary hover:underline">
          {t('students.backToMyCourses')}
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" onClick={() => navigate(-1)}>
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div>
          <h1 className="text-2xl font-bold">{t('students.title')}</h1>
          <p className="text-muted-foreground">{course.title}</p>
        </div>
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
          <CardTitle>{t('students.enrolledStudents')}</CardTitle>
          <CardDescription>
            {t('students.studentsEnrolled', { count: enrollments.length })}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {filteredEnrollments.length === 0 ? (
            <div className="text-center py-12">
              <Users className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
              <h3 className="font-medium text-lg mb-2">
                {search ? t('students.noStudents') : t('students.noStudentsYet')}
              </h3>
              <p className="text-muted-foreground">
                {search ? t('students.noStudentsSearch') : t('students.adjustSearch')}
              </p>
            </div>
          ) : (
            <div className="space-y-2">
              {filteredEnrollments.map((enrollment) => {
                const isExpanded = expandedStudentId === enrollment.student.id;
                return (
                  <div
                    key={enrollment.id}
                    className="rounded-xl border border-border/50 transition-colors"
                  >
                    <div
                      className="flex items-center gap-4 p-4 hover:bg-muted/30 cursor-pointer"
                      onClick={() => toggleExpand(enrollment.student.id)}
                    >
                      <Avatar>
                        {enrollment.student.avatar_url ? (
                          <AvatarImage
                            src={enrollment.student.avatar_url}
                            alt={enrollment.student.full_name}
                          />
                        ) : (
                          <AvatarFallback>
                            {(enrollment.student.first_name?.[0] ?? '').toUpperCase()}
                            {(enrollment.student.last_name?.[0] ?? '').toUpperCase()}
                          </AvatarFallback>
                        )}
                      </Avatar>
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
                            ? 'success'
                            : enrollment.status === 'completed'
                            ? 'default'
                            : 'outline'
                        }
                      >
                        {enrollment.status}
                      </Badge>
                      {enrollment.grade !== null && enrollment.grade !== undefined && (
                        <div className="text-right">
                          <div className="font-medium">{enrollment.grade}%</div>
                          <div className="text-xs text-muted-foreground">{t('students.grade')}</div>
                        </div>
                      )}
                      <Button variant="ghost" size="icon" className="shrink-0">
                        {isExpanded ? (
                          <ChevronUp className="h-4 w-4" />
                        ) : (
                          <ChevronDown className="h-4 w-4" />
                        )}
                      </Button>
                    </div>
                    {isExpanded && (
                      <div className="border-t border-border/50 p-4">
                        <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
                          <h4 className="text-sm font-medium">
                            {t('students.studentGrades')}
                          </h4>
                          <StudentTools courseId={course.id} student={enrollment.student} />
                        </div>
                        <StudentGrades studentId={enrollment.student.id} />
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
