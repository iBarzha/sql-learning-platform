import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Spinner } from '@/components/ui/spinner';
import { Plus, Users, BookOpen, Settings, Eye, EyeOff, GraduationCap, Layers, Copy } from 'lucide-react';
import { useCourses, useDuplicateCourse } from '@/hooks/queries/useCourses';

export function MyCoursesPage() {
  const { t } = useTranslation('instructor');
  const { data: coursesData, isLoading: loading } = useCourses();
  const courses = coursesData?.results ?? [];
  const duplicateMutation = useDuplicateCourse();

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
          <h1 className="text-3xl font-bold tracking-tight">{t('myCourses.title')}</h1>
          <p className="text-muted-foreground mt-1">
            {t('myCourses.subtitle')}
          </p>
        </div>
        <Link to="/courses/new">
          <Button className="gap-2">
            <Plus className="h-4 w-4" />
            {t('myCourses.newCourse')}
          </Button>
        </Link>
      </div>

      {courses.length === 0 ? (
        <Card className="border-dashed">
          <CardContent className="flex flex-col items-center justify-center py-16">
            <div className="h-16 w-16 rounded-2xl bg-primary/10 flex items-center justify-center mb-4">
              <BookOpen className="h-8 w-8 text-primary" />
            </div>
            <h3 className="font-semibold text-lg mb-2">{t('myCourses.noCourses')}</h3>
            <p className="text-muted-foreground text-center mb-6 max-w-sm">
              {t('myCourses.noCoursesDesc')}
            </p>
            <Link to="/courses/new">
              <Button className="gap-2">
                <Plus className="h-4 w-4" />
                {t('myCourses.createCourse')}
              </Button>
            </Link>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-5 md:grid-cols-2 lg:grid-cols-3">
          {courses.map((course) => (
            <Card key={course.id} className="group transition-all duration-200 hover:shadow-noble-lg hover:border-primary/20">
              <CardHeader className="pb-3">
                <div className="flex items-start justify-between gap-3">
                  <div className="h-11 w-11 rounded-xl bg-primary/10 flex items-center justify-center shrink-0 group-hover:bg-primary/20 transition-colors">
                    <GraduationCap className="h-5 w-5 text-primary" />
                  </div>
                  {course.is_published ? (
                    <Badge className="bg-accent/10 text-accent gap-1">
                      <Eye className="h-3 w-3" />
                      {t('myCourses.published')}
                    </Badge>
                  ) : (
                    <Badge variant="secondary" className="gap-1">
                      <EyeOff className="h-3 w-3" />
                      {t('myCourses.draft')}
                    </Badge>
                  )}
                </div>
                <CardTitle className="text-lg mt-3 line-clamp-1">{course.title}</CardTitle>
                <CardDescription className="line-clamp-2 mt-1">
                  {course.description || t('courseForm.description')}
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
                    <span>{t('myCourses.lessons', { count: course.lesson_count || 0 })}</span>
                  </div>
                  <Badge variant="outline" className="ml-auto">
                    {course.database_type}
                  </Badge>
                </div>
                <div className="flex gap-2">
                  <Link to={`/courses/${course.id}/manage`} className="flex-1">
                    <Button variant="outline" className="w-full gap-2">
                      <Settings className="h-4 w-4" />
                      {t('myCourses.manage')}
                    </Button>
                  </Link>
                  <Button
                    variant="ghost"
                    size="icon"
                    title={t('myCourses.duplicate')}
                    disabled={duplicateMutation.isPending}
                    onClick={() => duplicateMutation.mutate({ courseId: course.id })}
                  >
                    <Copy className="h-4 w-4" />
                  </Button>
                  <Link to={`/courses/${course.id}`}>
                    <Button variant="ghost" size="icon" title={t('myCourses.view')}>
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
