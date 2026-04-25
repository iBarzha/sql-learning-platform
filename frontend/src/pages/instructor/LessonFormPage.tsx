import { useEffect, useState } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useForm, useFieldArray, useWatch, type Control } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Spinner } from '@/components/ui/spinner';
import { Switch } from '@/components/ui/switch';
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from '@/components/ui/select';
import { ArrowLeft, Save, Plus, X, Paperclip, Trash2, ChevronDown, ChevronUp, ListChecks } from 'lucide-react';
import { useLesson, useCreateLesson, useUpdateLesson } from '@/hooks/queries/useLessons';
import { useCourseDatasets } from '@/hooks/queries/useCourses';
import { useModules } from '@/hooks/queries/useModules';
import { useAttachments, useUploadAttachment, useDeleteAttachment } from '@/hooks/queries/useAttachments';
import { lessonSchema, type LessonFormData } from '@/lib/schemas';
import { getApiErrorMessage } from '@/lib/utils';
import { SqlEditor } from '@/components/editor/SqlEditor';
import FileUpload, { formatFileSize, getFileTypeIcon } from '@/components/ui/FileUpload';

const LESSON_TYPES = [
  { value: 'theory', label: 'Theory', description: 'Educational content only' },
  { value: 'practice', label: 'Practice', description: 'SQL exercises only' },
  { value: 'mixed', label: 'Theory & Practice', description: 'Both content and exercises' },
];

const newExerciseDefaults = (order: number) => ({
  order,
  title: `Exercise ${order + 1}`,
  description: '',
  initial_code: '',
  expected_query: '',
  required_keywords: [],
  forbidden_keywords: [],
  order_matters: false,
  max_score: 100,
  hints: [],
  dataset_id: undefined,
});

interface ExerciseEditorProps {
  index: number;
  control: Control<LessonFormData>;
  setValue: ReturnType<typeof useForm<LessonFormData>>['setValue'];
  register: ReturnType<typeof useForm<LessonFormData>>['register'];
  datasets: Array<{ id: string; name: string }>;
  onRemove: () => void;
  canRemove: boolean;
  errors?: Record<string, { message?: string } | undefined>;
}

function ExerciseEditor({ index, control, setValue, register, datasets, onRemove, canRemove, errors }: ExerciseEditorProps) {
  const [collapsed, setCollapsed] = useState(false);
  const [newHint, setNewHint] = useState('');

  const exercise = useWatch({ control, name: `exercises.${index}` });
  const initialCode = exercise?.initial_code ?? '';
  const expectedQuery = exercise?.expected_query ?? '';
  const hints = exercise?.hints ?? [];

  function addHint() {
    if (newHint.trim()) {
      setValue(`exercises.${index}.hints`, [...hints, newHint.trim()]);
      setNewHint('');
    }
  }

  function removeHint(hi: number) {
    setValue(`exercises.${index}.hints`, hints.filter((_: string, i: number) => i !== hi));
  }

  return (
    <Card className="border-2">
      <CardHeader className="cursor-pointer" onClick={() => setCollapsed(!collapsed)}>
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2 text-base">
            <ListChecks className="h-4 w-4" />
            {exercise?.title || `Exercise ${index + 1}`}
          </CardTitle>
          <div className="flex items-center gap-1">
            {canRemove && (
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="text-destructive hover:text-destructive"
                onClick={(e) => {
                  e.stopPropagation();
                  onRemove();
                }}
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            )}
            <Button
              type="button"
              variant="ghost"
              size="icon"
              onClick={(e) => {
                e.stopPropagation();
                setCollapsed(!collapsed);
              }}
            >
              {collapsed ? <ChevronDown className="h-4 w-4" /> : <ChevronUp className="h-4 w-4" />}
            </Button>
          </div>
        </div>
      </CardHeader>
      {!collapsed && (
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label>Exercise Title *</Label>
            <Input {...register(`exercises.${index}.title`)} placeholder="e.g., Find all active users" />
            {errors?.title && <p className="text-sm text-destructive">{errors.title.message}</p>}
          </div>

          <div className="space-y-2">
            <Label>Dataset</Label>
            <Select
              value={exercise?.dataset_id ?? '__none__'}
              onValueChange={(val) => setValue(`exercises.${index}.dataset_id`, val === '__none__' ? undefined : val)}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__none__">No dataset</SelectItem>
                {datasets.map((ds) => (
                  <SelectItem key={ds.id} value={ds.id}>
                    {ds.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label>Task Description</Label>
            <Textarea
              {...register(`exercises.${index}.description`)}
              placeholder="Describe what the student needs to do..."
              rows={3}
            />
          </div>

          <div className="space-y-2">
            <Label>Initial Code (optional)</Label>
            <SqlEditor
              value={initialCode}
              onChange={(v) => setValue(`exercises.${index}.initial_code`, v)}
              height="80px"
              placeholder="-- Start writing your query here"
            />
          </div>

          <div className="space-y-2">
            <Label>Expected Query (for grading)</Label>
            <SqlEditor
              value={expectedQuery}
              onChange={(v) => setValue(`exercises.${index}.expected_query`, v)}
              height="80px"
              placeholder="SELECT * FROM users WHERE active = true;"
            />
          </div>

          <div className="space-y-2">
            <Label>Max Score</Label>
            <Input
              type="number"
              min="1"
              value={exercise?.max_score ?? 100}
              onChange={(e) => setValue(`exercises.${index}.max_score`, parseInt(e.target.value) || 100)}
            />
          </div>

          <div className="space-y-2">
            <Label>Hints</Label>
            <div className="space-y-1">
              {hints.map((hint: string, hi: number) => (
                <div key={hi} className="flex items-center gap-2 p-2 bg-muted rounded-md">
                  <span className="flex-1 text-sm">{hint}</span>
                  <Button type="button" variant="ghost" size="icon" onClick={() => removeHint(hi)}>
                    <X className="h-4 w-4" />
                  </Button>
                </div>
              ))}
            </div>
            <div className="flex gap-2">
              <Input
                value={newHint}
                onChange={(e) => setNewHint(e.target.value)}
                placeholder="Add a hint..."
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault();
                    addHint();
                  }
                }}
              />
              <Button type="button" variant="outline" onClick={addHint}>
                <Plus className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </CardContent>
      )}
    </Card>
  );
}

export function LessonFormPage() {
  const { t } = useTranslation('instructor');
  const { courseId, lessonId } = useParams<{ courseId: string; lessonId: string }>();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const preselectedModuleId = searchParams.get('module') ?? undefined;
  const isEditing = Boolean(lessonId);

  const { data: existingLesson, isLoading: lessonLoading } = useLesson(
    isEditing ? courseId : undefined,
    isEditing ? lessonId : undefined
  );
  const { data: datasets = [], isLoading: datasetsLoading } = useCourseDatasets(courseId);
  const { data: modules = [] } = useModules(courseId);
  const createLesson = useCreateLesson(courseId!);
  const updateLessonMutation = useUpdateLesson(courseId!, lessonId ?? '');
  const { data: attachments = [] } = useAttachments(
    isEditing ? courseId : undefined,
    isEditing ? lessonId : undefined,
  );
  const uploadAttachment = useUploadAttachment(courseId!, lessonId ?? '');
  const deleteAttachment = useDeleteAttachment(courseId!, lessonId ?? '');
  const loading = (isEditing ? lessonLoading : false) || datasetsLoading;

  const [apiError, setApiError] = useState('');

  const {
    register,
    handleSubmit,
    reset,
    setValue,
    watch,
    control,
    formState: { errors, isSubmitting },
  } = useForm<LessonFormData>({
    resolver: zodResolver(lessonSchema),
    defaultValues: {
      title: '',
      description: '',
      lesson_type: 'mixed',
      theory_content: '',
      time_limit_seconds: 600,
      max_attempts: undefined,
      exercises: [newExerciseDefaults(0)],
      module_id: preselectedModuleId ?? '',
      is_published: false,
    },
  });

  const { fields, append, remove } = useFieldArray({ control, name: 'exercises' });

  const lessonType = watch('lesson_type');
  const theoryContent = watch('theory_content') ?? '';

  useEffect(() => {
    if (existingLesson) {
      reset({
        title: existingLesson.title,
        description: existingLesson.description || '',
        lesson_type: existingLesson.lesson_type,
        theory_content: existingLesson.theory_content || '',
        time_limit_seconds: existingLesson.time_limit_seconds || 600,
        max_attempts: existingLesson.max_attempts ?? undefined,
        exercises: (existingLesson.exercises || []).map((ex, idx) => ({
          id: ex.id,
          order: ex.order ?? idx,
          title: ex.title,
          description: ex.description || '',
          initial_code: ex.initial_code || '',
          expected_query: ex.expected_query || '',
          required_keywords: ex.required_keywords || [],
          forbidden_keywords: ex.forbidden_keywords || [],
          order_matters: ex.order_matters || false,
          max_score: ex.max_score,
          hints: ex.hints || [],
          dataset_id: ex.dataset?.id ?? undefined,
        })),
        module_id: existingLesson.module ?? '',
        is_published: existingLesson.is_published,
      });
    }
  }, [existingLesson, reset]);

  async function onSubmit(data: LessonFormData) {
    setApiError('');
    try {
      const payload = {
        ...data,
        max_attempts: data.max_attempts ?? undefined,
        exercises: data.exercises.map((ex, idx) => ({
          ...ex,
          order: idx,
          dataset_id: ex.dataset_id ?? undefined,
        })),
      };
      if (isEditing) {
        await updateLessonMutation.mutateAsync(payload);
      } else {
        await createLesson.mutateAsync(payload);
      }
      navigate(`/courses/${courseId}/manage`);
    } catch (err) {
      setApiError(getApiErrorMessage(err, 'Failed to save lesson'));
    }
  }

  const showTheory = lessonType === 'theory' || lessonType === 'mixed';
  const showPractice = lessonType === 'practice' || lessonType === 'mixed';

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Spinner size="lg" />
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" onClick={() => navigate(-1)}>
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div>
          <h1 className="text-3xl font-bold">
            {isEditing ? 'Edit Lesson' : 'New Lesson'}
          </h1>
          <p className="text-muted-foreground">
            {isEditing ? 'Update lesson content' : 'Create a new lesson'}
          </p>
        </div>
      </div>

      {apiError && (
        <Alert variant="destructive">
          <AlertDescription>{apiError}</AlertDescription>
        </Alert>
      )}

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
        {/* Basic Info */}
        <Card>
          <CardHeader>
            <CardTitle>Basic Information</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="title">Title *</Label>
              <Input id="title" {...register('title')} placeholder="e.g., Introduction to SELECT" />
              {errors.title && <p className="text-sm text-destructive">{errors.title.message}</p>}
            </div>

            <div className="space-y-2">
              <Label htmlFor="description">Short Description</Label>
              <Input id="description" {...register('description')} placeholder="Brief description shown on the card" />
            </div>

            <div className="space-y-2">
              <Label>Lesson Type *</Label>
              <div className="grid gap-2 sm:grid-cols-3">
                {LESSON_TYPES.map((type) => (
                  <label
                    key={type.value}
                    className={`flex flex-col p-3 rounded-lg border cursor-pointer transition-colors ${
                      lessonType === type.value ? 'border-primary bg-primary/5' : 'hover:bg-muted'
                    }`}
                  >
                    <input type="radio" value={type.value} {...register('lesson_type')} className="sr-only" />
                    <span className="font-medium">{type.label}</span>
                    <span className="text-xs text-muted-foreground">{type.description}</span>
                  </label>
                ))}
              </div>
            </div>

            {modules.length === 0 ? (
              <Alert variant="destructive">
                <AlertDescription>{t('lessonForm.noModulesAvailable')}</AlertDescription>
              </Alert>
            ) : (
              <div className="space-y-2">
                <Label>{t('lessonForm.module')} *</Label>
                <Select
                  value={watch('module_id') || ''}
                  onValueChange={(val) => setValue('module_id', val, { shouldValidate: true })}
                >
                  <SelectTrigger>
                    <SelectValue placeholder={t('lessonForm.selectModule')} />
                  </SelectTrigger>
                  <SelectContent>
                    {modules.map((mod) => (
                      <SelectItem key={mod.id} value={mod.id}>
                        {mod.title}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {errors.module_id && (
                  <p className="text-sm text-destructive">{errors.module_id.message}</p>
                )}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Theory */}
        {showTheory && (
          <Card>
            <CardHeader>
              <CardTitle>Theory Content</CardTitle>
              <CardDescription>Educational material for this lesson</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                <Label>Content (Markdown supported)</Label>
                <SqlEditor
                  value={theoryContent}
                  onChange={(v) => setValue('theory_content', v)}
                  language="markdown"
                  height="256px"
                  placeholder="# Lesson Title&#10;&#10;Write your lesson content here using Markdown..."
                />
              </div>
            </CardContent>
          </Card>
        )}

        {/* Practice exercises */}
        {showPractice && (
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Practice Exercises</CardTitle>
                  <CardDescription>
                    Add one or more exercises. Students see a shared timer for the whole lesson.
                  </CardDescription>
                </div>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => append(newExerciseDefaults(fields.length))}
                >
                  <Plus className="h-4 w-4 mr-1" />
                  Add Exercise
                </Button>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label>Total Time Limit (seconds)</Label>
                  <Input
                    type="number"
                    min="1"
                    value={watch('time_limit_seconds')}
                    onChange={(e) => setValue('time_limit_seconds', parseInt(e.target.value) || 600)}
                  />
                  <p className="text-xs text-muted-foreground">
                    Shared timer running across all exercises (e.g., 600 = 10 minutes for all).
                  </p>
                </div>
                <div className="space-y-2">
                  <Label>Max Attempts (per exercise)</Label>
                  <Input
                    type="number"
                    min="1"
                    value={watch('max_attempts') ?? ''}
                    onChange={(e) =>
                      setValue('max_attempts', e.target.value ? parseInt(e.target.value) : undefined)
                    }
                    placeholder="Unlimited"
                  />
                </div>
              </div>

              <div className="space-y-3">
                {fields.map((field, idx) => (
                  <ExerciseEditor
                    key={field.id}
                    index={idx}
                    control={control}
                    setValue={setValue}
                    register={register}
                    datasets={datasets}
                    onRemove={() => remove(idx)}
                    canRemove={fields.length > 1}
                    errors={errors.exercises?.[idx] as Record<string, { message?: string } | undefined>}
                  />
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Attachments (edit mode only) */}
        {isEditing && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Paperclip className="h-4 w-4" />
                Attachments
              </CardTitle>
              <CardDescription>Upload PDFs, images, or code files for students</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {attachments.length > 0 && (
                <div className="space-y-2">
                  {attachments.map((att) => (
                    <div key={att.id} className="flex items-center gap-3 p-2 bg-muted rounded-md">
                      <span>{getFileTypeIcon(att.file_type)}</span>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium truncate">{att.filename}</p>
                        <p className="text-xs text-muted-foreground">
                          {formatFileSize(att.file_size)}
                        </p>
                      </div>
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        onClick={() => deleteAttachment.mutate(att.id)}
                        disabled={deleteAttachment.isPending}
                      >
                        <Trash2 className="h-4 w-4 text-destructive" />
                      </Button>
                    </div>
                  ))}
                </div>
              )}
              <FileUpload
                onUpload={(file) => uploadAttachment.mutate(file)}
                isUploading={uploadAttachment.isPending}
              />
            </CardContent>
          </Card>
        )}

        {/* Actions */}
        <div className="flex justify-between">
          <div className="flex items-center gap-3">
            <Switch
              checked={watch('is_published')}
              onCheckedChange={(checked) => setValue('is_published', checked)}
            />
            <Label className="text-sm cursor-pointer">{t('lessonForm.publishImmediately')}</Label>
          </div>
          <div className="flex gap-2">
            <Button type="button" variant="outline" onClick={() => navigate(-1)}>
              Cancel
            </Button>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? (
                <Spinner size="sm" className="mr-2" />
              ) : (
                <Save className="h-4 w-4 mr-2" />
              )}
              {isEditing ? 'Save Changes' : 'Create Lesson'}
            </Button>
          </div>
        </div>
      </form>
    </div>
  );
}
