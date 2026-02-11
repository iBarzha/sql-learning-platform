import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Spinner } from '@/components/ui/spinner';
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from '@/components/ui/select';
import { ArrowLeft, Save } from 'lucide-react';
import { courseSchema, type CourseFormData } from '@/lib/schemas';
import { getApiErrorMessage } from '@/lib/utils';
import { useCourse, useCreateCourse, useUpdateCourse } from '@/hooks/queries/useCourses';

const DATABASE_TYPES = [
  { value: 'postgresql', label: 'PostgreSQL' },
  { value: 'sqlite', label: 'SQLite' },
  { value: 'mysql', label: 'MySQL' },
  { value: 'mariadb', label: 'MariaDB' },
  { value: 'mongodb', label: 'MongoDB' },
  { value: 'redis', label: 'Redis' },
];

export function CourseFormPage() {
  const { t } = useTranslation('instructor');
  const { courseId } = useParams<{ courseId: string }>();
  const navigate = useNavigate();
  const isEditing = Boolean(courseId);

  const { data: existingCourse, isLoading: loading } = useCourse(isEditing ? courseId : undefined);
  const createCourse = useCreateCourse();
  const updateCourseMutation = useUpdateCourse(courseId!);

  const [apiError, setApiError] = useState('');

  const {
    register,
    handleSubmit,
    reset,
    setValue,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<CourseFormData>({
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    resolver: zodResolver(courseSchema) as any,
    defaultValues: {
      title: '',
      description: '',
      database_type: 'postgresql',
      max_students: undefined,
      start_date: '',
      end_date: '',
    },
  });

  // Populate form when course data loads
  useEffect(() => {
    if (existingCourse) {
      reset({
        title: existingCourse.title,
        description: existingCourse.description,
        database_type: existingCourse.database_type,
        max_students: existingCourse.max_students ?? undefined,
        start_date: existingCourse.start_date || '',
        end_date: existingCourse.end_date || '',
      });
    }
  }, [existingCourse, reset]);

  async function onSubmit(data: CourseFormData) {
    setApiError('');
    try {
      const payload = {
        ...data,
        max_students: data.max_students || undefined,
        start_date: data.start_date || undefined,
        end_date: data.end_date || undefined,
      };

      if (isEditing) {
        await updateCourseMutation.mutateAsync(payload);
        navigate(`/courses/${courseId}/manage`);
      } else {
        const course = await createCourse.mutateAsync(payload);
        navigate(`/courses/${course.id}/manage`);
      }
    } catch (err) {
      setApiError(getApiErrorMessage(err, t('courseForm.failedSave')));
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
    <div className="max-w-2xl mx-auto space-y-6">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" onClick={() => navigate(-1)}>
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div>
          <h1 className="text-3xl font-bold">
            {isEditing ? t('courseForm.editTitle') : t('courseForm.createTitle')}
          </h1>
          <p className="text-muted-foreground">
            {isEditing ? t('courseForm.editSubtitle') : t('courseForm.createSubtitle')}
          </p>
        </div>
      </div>

      {apiError && (
        <Alert variant="destructive">
          <AlertDescription>{apiError}</AlertDescription>
        </Alert>
      )}

      <form onSubmit={handleSubmit(onSubmit)}>
        <Card>
          <CardHeader>
            <CardTitle>{t('courseForm.courseDetails')}</CardTitle>
            <CardDescription>{t('courseForm.courseDetailsDesc')}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="title">{t('courseForm.titleRequired')}</Label>
              <Input
                id="title"
                {...register('title')}
                placeholder={t('courseForm.titlePlaceholder')}
              />
              {errors.title && (
                <p className="text-sm text-destructive">{errors.title.message}</p>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="description">{t('courseForm.description')}</Label>
              <Textarea
                id="description"
                {...register('description')}
                placeholder={t('courseForm.descriptionPlaceholder')}
                rows={4}
              />
            </div>

            <div className="space-y-2">
              <Label>{t('courseForm.databaseType')} *</Label>
              <Select value={watch('database_type')} onValueChange={(val) => setValue('database_type', val)}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {DATABASE_TYPES.map((type) => (
                    <SelectItem key={type.value} value={type.value}>
                      {type.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {errors.database_type && (
                <p className="text-sm text-destructive">{errors.database_type.message}</p>
              )}
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="start_date">{t('courseForm.startDate')}</Label>
                <Input id="start_date" type="date" {...register('start_date')} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="end_date">{t('courseForm.endDate')}</Label>
                <Input id="end_date" type="date" {...register('end_date')} />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="mt-4">
          <CardHeader>
            <CardTitle>{t('courseForm.enrollmentSettings')}</CardTitle>
            <CardDescription>{t('courseForm.enrollmentSettingsDesc')}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="max_students">{t('courseForm.maxStudents')}</Label>
              <Input
                id="max_students"
                type="number"
                min="1"
                value={watch('max_students') ?? ''}
                onChange={(e) =>
                  setValue(
                    'max_students',
                    e.target.value ? parseInt(e.target.value) : undefined
                  )
                }
                placeholder={t('courseForm.unlimitedPlaceholder')}
              />
            </div>
          </CardContent>
        </Card>

        <div className="flex justify-end gap-2 mt-6">
          <Button type="button" variant="outline" onClick={() => navigate(-1)}>
            {t('courseForm.cancel')}
          </Button>
          <Button type="submit" disabled={isSubmitting}>
            {isSubmitting ? (
              <Spinner size="sm" className="mr-2" />
            ) : (
              <Save className="h-4 w-4 mr-2" />
            )}
            {isEditing ? t('courseForm.saveCourse') : t('courseForm.createCourse')}
          </Button>
        </div>
      </form>
    </div>
  );
}
