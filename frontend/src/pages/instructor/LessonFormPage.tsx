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
import { ArrowLeft, Save, Plus, X, Paperclip, Trash2, ChevronDown, ChevronUp, ListChecks, ShieldCheck } from 'lucide-react';
import { useLesson, useCreateLesson, useUpdateLesson, useValidateExercises } from '@/hooks/queries/useLessons';
import type { LessonValidation } from '@/api/lessons';
import { useMyDatasets, useCourseDatasets } from '@/hooks/queries/useDatasets';
import { useModules } from '@/hooks/queries/useModules';
import { useAttachments, useUploadAttachment, useDeleteAttachment } from '@/hooks/queries/useAttachments';
import { lessonSchema, type LessonFormData } from '@/lib/schemas';
import { getApiErrorMessage } from '@/lib/utils';
import { SqlEditor } from '@/components/editor/SqlEditor';
import FileUpload, { formatFileSize, getFileTypeIcon } from '@/components/ui/FileUpload';
import { CriteriaEditor } from '@/components/grading/CriteriaEditor';
import { ExerciseValidationReport } from '@/components/instructor/ExerciseValidationReport';
import { useCriteriaCatalog } from '@/hooks/queries/useGrading';
import { useCourse } from '@/hooks/queries/useCourses';
import { applicableCriteria, derivedCriteria, detectKind } from '@/lib/criteria';
import type { CriterionInfo } from '@/types';

const LESSON_TYPES = [
  { value: 'theory', label: 'lessonForm.types.theory', description: 'lessonForm.types.theoryDesc' },
  { value: 'practice', label: 'lessonForm.types.practice', description: 'lessonForm.types.practiceDesc' },
  { value: 'mixed', label: 'lessonForm.types.mixed', description: 'lessonForm.types.mixedDesc' },
];

const newExerciseDefaults = (order: number, title: string) => ({
  order,
  title,
  description: '',
  initial_code: '',
  expected_query: '',
  required_keywords: [],
  forbidden_keywords: [],
  order_matters: false,
  ignore_column_order: false,
  max_score: 100,
  hints: [],
  check_datasets: [],
  criteria: { enabled: [], threshold: 0 },
  dataset_id: undefined,
});

type CheckDatasetForm = LessonFormData['exercises'][number]['check_datasets'][number];

interface ExerciseEditorProps {
  index: number;
  control: Control<LessonFormData>;
  setValue: ReturnType<typeof useForm<LessonFormData>>['setValue'];
  register: ReturnType<typeof useForm<LessonFormData>>['register'];
  datasets: Array<{ id: string; name: string }>;
  dbType: string;
  catalog: CriterionInfo[];
  onRemove: () => void;
  canRemove: boolean;
  errors?: Record<string, { message?: string } | undefined>;
}

function ExerciseEditor({ index, control, setValue, register, datasets, dbType, catalog, onRemove, canRemove, errors }: ExerciseEditorProps) {
  const { t } = useTranslation('instructor');
  const [collapsedByUser, setCollapsedByUser] = useState(false);
  // A field error inside a collapsed exercise would be invisible, so errors keep it open.
  const collapsed = collapsedByUser && !errors;
  const [newHint, setNewHint] = useState('');

  const exercise = useWatch({ control, name: `exercises.${index}` });
  const initialCode = exercise?.initial_code ?? '';
  const expectedQuery = exercise?.expected_query ?? '';
  const hints = exercise?.hints ?? [];

  const criteriaKind = detectKind(expectedQuery, dbType);
  const hasReference = Boolean(expectedQuery.trim());
  // Exercises saved before criteria existed carry `{}`; an empty list means server defaults.
  const criteriaValue = {
    enabled: exercise?.criteria?.enabled ?? [],
    threshold: exercise?.criteria?.threshold ?? 0,
  };

  function addHint() {
    if (newHint.trim()) {
      setValue(`exercises.${index}.hints`, [...hints, newHint.trim()]);
      setNewHint('');
    }
  }

  function removeHint(hi: number) {
    setValue(`exercises.${index}.hints`, hints.filter((_: string, i: number) => i !== hi));
  }

  const checkDatasets: CheckDatasetForm[] = exercise?.check_datasets ?? [];

  function addCheckDataset() {
    setValue(`exercises.${index}.check_datasets`, [
      ...checkDatasets,
      { name: '', seed_sql: '', targets: '' },
    ]);
  }

  function updateCheckDataset(di: number, patch: Partial<CheckDatasetForm>) {
    setValue(
      `exercises.${index}.check_datasets`,
      checkDatasets.map((ds, i) => (i === di ? { ...ds, ...patch } : ds))
    );
  }

  function removeCheckDataset(di: number) {
    setValue(
      `exercises.${index}.check_datasets`,
      checkDatasets.filter((_, i) => i !== di)
    );
  }

  return (
    <Card className="border-2">
      <CardHeader className="cursor-pointer" onClick={() => setCollapsedByUser(!collapsed)}>
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2 text-base">
            <ListChecks className="h-4 w-4" />
            {exercise?.title || t('lessonForm.exerciseDefaultTitle', { n: index + 1 })}
          </CardTitle>
          <div className="flex items-center gap-1">
            {canRemove && (
              <Button
                type="button"
                variant="ghost"
                size="icon"
                aria-label={t('lessonForm.removeExercise')}
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
              aria-label={collapsed ? t('lessonForm.expandExercise') : t('lessonForm.collapseExercise')}
              onClick={(e) => {
                e.stopPropagation();
                setCollapsedByUser(!collapsed);
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
            <Label>{t('lessonForm.exerciseTitle')} *</Label>
            <Input {...register(`exercises.${index}.title`)} placeholder={t('lessonForm.exerciseTitlePlaceholder')} />
            {errors?.title && <p className="text-sm text-destructive">{errors.title.message}</p>}
          </div>

          <div className="space-y-2">
            <Label>{t('lessonForm.datasetLabel')}</Label>
            <Select
              value={exercise?.dataset_id ?? '__none__'}
              onValueChange={(val) => setValue(`exercises.${index}.dataset_id`, val === '__none__' ? undefined : val)}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__none__">{t('lessonForm.noDataset')}</SelectItem>
                {datasets.map((ds) => (
                  <SelectItem key={ds.id} value={ds.id}>
                    {ds.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label>{t('lessonForm.taskDescription')}</Label>
            <Textarea
              {...register(`exercises.${index}.description`)}
              placeholder={t('lessonForm.taskPlaceholder')}
              rows={3}
            />
          </div>

          <div className="space-y-2">
            <Label>{t('lessonForm.initialCode')}</Label>
            <SqlEditor
              value={initialCode}
              onChange={(v) => setValue(`exercises.${index}.initial_code`, v)}
              height="80px"
              placeholder={t('lessonForm.initialCodePlaceholder')}
            />
          </div>

          <div className="space-y-2">
            <Label>{t('lessonForm.expectedQuery')}</Label>
            <SqlEditor
              value={expectedQuery}
              onChange={(v) => setValue(`exercises.${index}.expected_query`, v)}
              height="80px"
              placeholder="SELECT * FROM users WHERE active = true;"
            />
            {errors?.expected_query && (
              <p className="text-sm text-destructive">{t('lessonForm.errors.expectedQueryRequired')}</p>
            )}
          </div>

          <div className="flex items-start gap-3">
            <Switch
              id={`exercise-${index}-ignore-column-order`}
              checked={exercise?.ignore_column_order ?? false}
              onCheckedChange={(checked) => setValue(`exercises.${index}.ignore_column_order`, checked)}
            />
            <div className="space-y-1">
              <Label htmlFor={`exercise-${index}-ignore-column-order`} className="cursor-pointer">
                {t('lessonForm.ignoreColumnOrder')}
              </Label>
              <p className="text-xs text-muted-foreground">{t('lessonForm.ignoreColumnOrderDesc')}</p>
            </div>
          </div>

          <div className="space-y-2">
            <Label>{t('lessonForm.maxScore')}</Label>
            <Input
              type="number"
              min="1"
              value={exercise?.max_score ?? 100}
              onChange={(e) => setValue(`exercises.${index}.max_score`, parseInt(e.target.value) || 100)}
            />
          </div>

          <div className="space-y-2">
            <Label>{t('lessonForm.hints')}</Label>
            <div className="space-y-1">
              {hints.map((hint: string, hi: number) => (
                <div key={hi} className="flex items-center gap-2 p-2 bg-muted rounded-md">
                  <span className="flex-1 text-sm">{hint}</span>
                  <Button type="button" variant="ghost" size="icon" aria-label={t('lessonForm.removeHint')} onClick={() => removeHint(hi)}>
                    <X className="h-4 w-4" />
                  </Button>
                </div>
              ))}
            </div>
            <div className="flex gap-2">
              <Input
                value={newHint}
                onChange={(e) => setNewHint(e.target.value)}
                placeholder={t('lessonForm.hintPlaceholder')}
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

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label>{t('lessonForm.hiddenDatasets')}</Label>
              <Button type="button" variant="outline" size="sm" onClick={addCheckDataset}>
                <Plus className="h-4 w-4 mr-1" />
                {t('lessonForm.addDataset')}
              </Button>
            </div>
            <p className="text-xs text-muted-foreground">{t('lessonForm.hiddenDatasetsDesc')}</p>
            {checkDatasets.length === 0 && (
              <p className="text-xs text-muted-foreground">{t('lessonForm.noHiddenDatasetsHint')}</p>
            )}
            {checkDatasets.map((ds, di) => (
              <div key={di} className="space-y-2 p-3 border rounded-md">
                <div className="flex gap-2">
                  <Input
                    value={ds.name}
                    placeholder={t('lessonForm.datasetNamePlaceholder')}
                    onChange={(e) => updateCheckDataset(di, { name: e.target.value })}
                  />
                  <Input
                    value={ds.targets ?? ''}
                    placeholder={t('lessonForm.datasetTargetsPlaceholder')}
                    onChange={(e) => updateCheckDataset(di, { targets: e.target.value })}
                  />
                  <Button type="button" variant="ghost" size="icon" aria-label={t('lessonForm.removeDataset')} onClick={() => removeCheckDataset(di)}>
                    <X className="h-4 w-4" />
                  </Button>
                </div>
                <Textarea
                  value={ds.seed_sql}
                  rows={4}
                  placeholder={t('lessonForm.datasetSeedPlaceholder')}
                  onChange={(e) => updateCheckDataset(di, { seed_sql: e.target.value })}
                />
              </div>
            ))}
          </div>

          <div className="space-y-2">
            <Label>{t('lessonForm.criteriaTitle')}</Label>
            <p className="text-xs text-muted-foreground">{t('lessonForm.criteriaDesc')}</p>
            <CriteriaEditor
              value={criteriaValue}
              onChange={(v) => setValue(`exercises.${index}.criteria`, v, { shouldDirty: true })}
              catalog={catalog}
              kind={criteriaKind}
              expectedQuery={expectedQuery}
              hasReference={hasReference}
              derived={derivedCriteria(
                {
                  check_datasets: checkDatasets,
                  required_keywords: exercise?.required_keywords ?? [],
                  forbidden_keywords: exercise?.forbidden_keywords ?? [],
                  expected_query: expectedQuery,
                },
                criteriaKind
              )}
            />
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
  const { data: myDatasets = [], isLoading: datasetsLoading } = useMyDatasets();
  const { data: courseDatasets = [] } = useCourseDatasets(courseId);
  // Datasets created inside this course live under the course, not in the
  // instructor's library; the exercise picker should offer both.
  const datasets = [...courseDatasets, ...myDatasets].filter(
    (ds, i, all) => all.findIndex((d) => d.id === ds.id) === i
  );
  const { data: modules = [] } = useModules(courseId);
  const { data: course } = useCourse(courseId);
  const { data: catalog = [] } = useCriteriaCatalog();
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
  const [validation, setValidation] = useState<LessonValidation | null>(null);
  const validateExercises = useValidateExercises(courseId!, lessonId ?? '');

  async function runValidation() {
    setApiError('');
    try {
      setValidation(await validateExercises.mutateAsync());
    } catch (err) {
      setApiError(getApiErrorMessage(err, t('lessonForm.errors.validateFailed')));
    }
  }

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
      time_limit_seconds: null,
      max_attempts: undefined,
      exercises: [newExerciseDefaults(0, t('lessonForm.exerciseDefaultTitle', { n: 1 }))],
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
        time_limit_seconds: existingLesson.time_limit_seconds ?? null,
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
          ignore_column_order: ex.ignore_column_order ?? false,
          max_score: ex.max_score,
          hints: ex.hints || [],
          check_datasets: ex.check_datasets || [],
          criteria: { enabled: ex.criteria?.enabled ?? [], threshold: ex.criteria?.threshold ?? 0 },
          dataset_id: ex.dataset?.id ?? undefined,
        })),
        module_id: existingLesson.module ?? '',
        is_published: existingLesson.is_published,
      });
    }
  }, [existingLesson, reset]);

  async function onSubmit(data: LessonFormData) {
    setApiError('');
    // A theory lesson hides its exercises: they are not validated, and an edit leaves
    // the stored ones untouched instead of resending them.
    const isTheory = data.lesson_type === 'theory';
    const incomplete = isTheory ? -1 : data.exercises.findIndex((ex) =>
      (ex.check_datasets ?? []).some((ds) => !ds.name.trim() || !ds.seed_sql.trim())
    );
    if (incomplete !== -1) {
      setApiError(t('lessonForm.errors.incompleteDataset', { n: incomplete + 1 }));
      return;
    }
    try {
      const exercises = data.exercises.map((ex, idx) => ({
        ...ex,
        order: idx,
        dataset_id: ex.dataset_id ?? undefined,
        // A stored choice can outlive the reference it was made for (ORDER BY removed):
        // send only ids that still apply, the same way grading would treat them.
        criteria: {
          enabled: (ex.criteria?.enabled ?? []).filter((id) =>
            applicableCriteria(
              catalog,
              detectKind(ex.expected_query ?? '', course?.database_type ?? 'sqlite'),
              ex.expected_query ?? '',
              Boolean(ex.expected_query?.trim())
            ).some((c) => c.id === id)
          ),
          threshold: ex.criteria?.threshold ?? 0,
        },
      }));
      const payload = {
        ...data,
        max_attempts: data.max_attempts ?? undefined,
        exercises: isTheory ? (isEditing ? undefined : []) : exercises,
      };
      if (isEditing) {
        await updateLessonMutation.mutateAsync(payload);
      } else {
        await createLesson.mutateAsync(payload);
      }
      navigate(`/courses/${courseId}/manage`);
    } catch (err) {
      setApiError(getApiErrorMessage(err, t('lessonForm.errors.saveFailed')));
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
            {isEditing ? t('lessonForm.editTitle') : t('lessonForm.createTitle')}
          </h1>
          <p className="text-muted-foreground">
            {isEditing ? t('lessonForm.editSubtitle') : t('lessonForm.createSubtitle')}
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
            <CardTitle>{t('lessonForm.basicInfo')}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="title">{t('lessonForm.titleLabel')} *</Label>
              <Input id="title" {...register('title')} placeholder={t('lessonForm.titlePlaceholder')} />
              {errors.title && <p className="text-sm text-destructive">{errors.title.message}</p>}
            </div>

            <div className="space-y-2">
              <Label htmlFor="description">{t('lessonForm.descriptionLabel')}</Label>
              <Input id="description" {...register('description')} placeholder={t('lessonForm.descriptionPlaceholder')} />
            </div>

            <div className="space-y-2">
              <Label>{t('lessonForm.lessonType')} *</Label>
              <div className="grid gap-2 sm:grid-cols-3">
                {LESSON_TYPES.map((type) => (
                  <label
                    key={type.value}
                    className={`flex flex-col p-3 rounded-lg border cursor-pointer transition-colors ${
                      lessonType === type.value ? 'border-primary bg-primary/5' : 'hover:bg-muted'
                    }`}
                  >
                    <input type="radio" value={type.value} {...register('lesson_type')} className="sr-only" />
                    <span className="font-medium">{t(type.label)}</span>
                    <span className="text-xs text-muted-foreground">{t(type.description)}</span>
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
                  onValueChange={(val) => {
                    // Radix Select emits '' when its controlled value is replaced by
                    // reset(); that is not a user action and must not wipe the field.
                    if (val) setValue('module_id', val, { shouldValidate: true });
                  }}
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
              <CardTitle>{t('lessonForm.theoryContent')}</CardTitle>
              <CardDescription>{t('lessonForm.theoryContentDesc')}</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                <Label>{t('lessonForm.markdown')}</Label>
                <SqlEditor
                  value={theoryContent}
                  onChange={(v) => setValue('theory_content', v)}
                  language="markdown"
                  height="256px"
                  placeholder={t('lessonForm.theoryPlaceholder')}
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
                  <CardTitle>{t('lessonForm.practiceExercises')}</CardTitle>
                  <CardDescription>{t('lessonForm.practiceExercisesDesc')}</CardDescription>
                </div>
                <div className="flex items-center gap-2">
                  {isEditing && (
                    <Button
                      type="button"
                      variant="secondary"
                      size="sm"
                      disabled={validateExercises.isPending}
                      onClick={runValidation}
                    >
                      <ShieldCheck className="h-4 w-4 mr-1" />
                      {validateExercises.isPending ? t('lessonForm.checking') : t('lessonForm.checkDatasets')}
                    </Button>
                  )}
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => append(newExerciseDefaults(fields.length, t('lessonForm.exerciseDefaultTitle', { n: fields.length + 1 })))}
                  >
                    <Plus className="h-4 w-4 mr-1" />
                    {t('lessonForm.addExercise')}
                  </Button>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label>{t('lessonForm.timeLimitMinutes')}</Label>
                  <Input
                    type="number"
                    min="1"
                    placeholder={t('lessonForm.unlimited')}
                    value={watch('time_limit_seconds') ? Math.round((watch('time_limit_seconds') as number) / 60) : ''}
                    onChange={(e) => {
                      const minutes = parseInt(e.target.value);
                      setValue('time_limit_seconds', Number.isFinite(minutes) && minutes > 0 ? minutes * 60 : null);
                    }}
                  />
                  <p className="text-xs text-muted-foreground">{t('lessonForm.timeLimitDesc')}</p>
                </div>
                <div className="space-y-2">
                  <Label>{t('lessonForm.maxAttemptsPerExercise')}</Label>
                  <Input
                    type="number"
                    min="1"
                    value={watch('max_attempts') ?? ''}
                    onChange={(e) =>
                      setValue('max_attempts', e.target.value ? parseInt(e.target.value) : undefined)
                    }
                    placeholder={t('lessonForm.unlimited')}
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
                    dbType={course?.database_type ?? 'sqlite'}
                    catalog={catalog}
                    onRemove={() => remove(idx)}
                    canRemove={fields.length > 1}
                    errors={errors.exercises?.[idx] as Record<string, { message?: string } | undefined>}
                  />
                ))}
              </div>

              {validation && (
                <ExerciseValidationReport validation={validation} onHide={() => setValidation(null)} />
              )}
            </CardContent>
          </Card>
        )}

        {/* Attachments (edit mode only) */}
        {isEditing && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Paperclip className="h-4 w-4" />
                {t('lessonForm.attachments')}
              </CardTitle>
              <CardDescription>{t('lessonForm.attachmentsDesc')}</CardDescription>
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
                        aria-label={t('lessonForm.deleteAttachment')}
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
              {t('lessonForm.cancel')}
            </Button>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? (
                <Spinner size="sm" className="mr-2" />
              ) : (
                <Save className="h-4 w-4 mr-2" />
              )}
              {isEditing ? t('lessonForm.saveChanges') : t('lessonForm.createLesson')}
            </Button>
          </div>
        </div>
      </form>
    </div>
  );
}
