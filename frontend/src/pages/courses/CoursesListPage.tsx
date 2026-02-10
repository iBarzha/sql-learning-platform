import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuthStore } from '@/store/authStore';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Plus, Search, Users, BookOpen, GraduationCap, CheckCircle } from 'lucide-react';
import { useCourses } from '@/hooks/queries/useCourses';

export function CoursesListPage() {
  const { t } = useTranslation('courses');
  const { user } = useAuthStore();
  const [search, setSearch] = useState('');
  const { data: coursesData, isLoading: loading } = useCourses({ is_published: true });
  const courses = coursesData?.results ?? [];

  const filteredCourses = courses.filter(
    (course) =>
      course.title.toLowerCase().includes(search.toLowerCase()) ||
      (course.description ?? '').toLowerCase().includes(search.toLowerCase()) ||
      (course.instructor_name ?? '').toLowerCase().includes(search.toLowerCase())
  );

  const isInstructor = user?.role === 'instructor' || user?.role === 'admin';

  return (
    <div className="space-y-8 animate-fade-in">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">{t('list.title')}</h1>
          <p className="text-muted-foreground mt-1">
            {t('list.subtitle')}
          </p>
        </div>
        {isInstructor && (
          <Link to="/courses/new">
            <Button className="gap-2">
              <Plus className="h-4 w-4" />
              {t('list.createCourse')}
            </Button>
          </Link>
        )}
      </div>

      <div className="relative max-w-md">
        <Search className="absolute left-4 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          placeholder={t('list.searchPlaceholder')}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="pl-11 h-11 rounded-xl bg-card border-border/50"
        />
      </div>

      {loading ? (
        <div className="grid gap-5 md:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Card key={i} className="h-full">
              <CardHeader className="pb-3">
                <div className="flex items-start justify-between gap-3">
                  <Skeleton className="h-11 w-11 rounded-xl" />
                  <Skeleton className="h-5 w-20 rounded-full" />
                </div>
                <Skeleton className="h-5 w-3/4 mt-3" />
                <Skeleton className="h-4 w-full mt-2" />
              </CardHeader>
              <CardContent className="pt-0">
                <div className="flex items-center justify-between mb-3">
                  <Skeleton className="h-4 w-24" />
                  <Skeleton className="h-4 w-10" />
                </div>
                <Skeleton className="h-4 w-20" />
              </CardContent>
            </Card>
          ))}
        </div>
      ) : filteredCourses.length === 0 ? (
        <Card className="border-dashed">
          <CardContent className="flex flex-col items-center justify-center py-16">
            <div className="h-16 w-16 rounded-2xl bg-primary/10 flex items-center justify-center mb-4">
              <BookOpen className="h-8 w-8 text-primary" />
            </div>
            <h3 className="font-semibold text-lg mb-2">{t('list.noCourses')}</h3>
            <p className="text-muted-foreground text-center max-w-sm">
              {search
                ? t('list.noCoursesSearch')
                : t('list.noCoursesAvailable')}
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-5 md:grid-cols-2 lg:grid-cols-3">
          {filteredCourses.map((course) => (
            <Link key={course.id} to={`/courses/${course.id}`} className="group">
              <Card className="h-full transition-all duration-200 group-hover:shadow-noble-lg group-hover:border-primary/20">
                <CardHeader className="pb-3">
                  <div className="flex items-start justify-between gap-3">
                    <div className="h-11 w-11 rounded-xl bg-primary/10 flex items-center justify-center shrink-0 group-hover:bg-primary/20 transition-colors">
                      <GraduationCap className="h-5 w-5 text-primary" />
                    </div>
                    <Badge variant="secondary" className="shrink-0 font-normal">
                      {course.database_type}
                    </Badge>
                  </div>
                  <CardTitle className="text-lg mt-3 group-hover:text-primary transition-colors line-clamp-2">
                    {course.title}
                  </CardTitle>
                  <CardDescription className="line-clamp-2 mt-1">
                    {course.description || t('list.noDescription')}
                  </CardDescription>
                </CardHeader>
                <CardContent className="pt-0">
                  <div className="flex items-center justify-between text-sm text-muted-foreground mb-3">
                    <span className="truncate">{course.instructor_name}</span>
                    <div className="flex items-center gap-1.5 shrink-0">
                      <Users className="h-4 w-4" />
                      <span>{course.student_count || 0}</span>
                    </div>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">
                      {t('list.lessonCount', { count: course.lesson_count || 0 })}
                    </span>
                    {course.is_enrolled && (
                      <Badge className="bg-accent text-accent-foreground gap-1">
                        <CheckCircle className="h-3 w-3" />
                        {t('list.enrolled')}
                      </Badge>
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
