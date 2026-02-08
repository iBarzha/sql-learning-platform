import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Spinner } from '@/components/ui/spinner';
import { ArrowLeft, Save, Plus, X } from 'lucide-react';
import { useLesson, useCreateLesson, useUpdateLesson } from '@/hooks/queries/useLessons';
import { useCourseDatasets } from '@/hooks/queries/useCourses';
import { useModules } from '@/hooks/queries/useModules';
import { lessonSchema, type LessonFormData } from '@/lib/schemas';
import { getApiErrorMessage } from '@/lib/utils';
import { SqlEditor } from '@/components/editor/SqlEditor';

const LESSON_TYPES = [
  { value: 'theory', label: 'Theory', description: 'Educational content only' },
  { value: 'practice', label: 'Practice', description: 'SQL exercises only' },
  { value: 'mixed', label: 'Theory & Practice', description: 'Both content and exercises' },
];

export function LessonFormPage() {
  const { courseId, lessonId } = useParams<{ courseId: string; lessonId: string }>();
  const navigate = useNavigate();
  const isEditing = Boolean(lessonId);

  const { data: existingLesson, isLoading: lessonLoading } = useLesson(
    isEditing ? courseId : undefined,
    isEditing ? lessonId : undefined
  );
  const { data: datasets = [], isLoading: datasetsLoading } = useCourseDatasets(courseId);
  const { data: modules = [] } = useModules(courseId);
  const createLesson = useCreateLesson(courseId!);
  const updateLessonMutation = useUpdateLesson(courseId!, lessonId ?? '');
  const loading = (isEditing ? lessonLoading : false) || datasetsLoading;

  const [apiError, setApiError] = useState('');
  const [newHint, setNewHint] = useState('');

  const {
    register,
    handleSubmit,
    reset,
    setValue,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<LessonFormData>({
    resolver: zodResolver(lessonSchema),
    defaultValues: {
      title: '',
      description: '',
      lesson_type: 'mixed',
      theory_content: '',
      practice_description: '',
      practice_initial_code: '',
      expected_query: '',
      required_keywords: [],
      forbidden_keywords: [],
      order_matters: false,
      max_score: 100,
      time_limit_seconds: 60,
      max_attempts: undefined,
      hints: [],
      dataset_id: undefined,
      module_id: undefined,
      is_published: false,
    },
  });

  const lessonType = watch('lesson_type');
  const hints = watch('hints') ?? [];
  const theoryContent = watch('theory_content') ?? '';
  const practiceInitialCode = watch('practice_initial_code') ?? '';
  const expectedQuery = watch('expected_query') ?? '';

  // Populate form when lesson data loads
  useEffect(() => {
    if (existingLesson) {
      reset({
        title: existingLesson.title,
        description: existingLesson.description || '',
        lesson_type: existingLesson.lesson_type,
        theory_content: existingLesson.theory_content || '',
        practice_description: existingLesson.practice_description || '',
        practice_initial_code: existingLesson.practice_initial_code || '',
        expected_query: existingLesson.expected_query || '',
        required_keywords: existingLesson.required_keywords || [],
        forbidden_keywords: existingLesson.forbidden_keywords || [],
        order_matters: existingLesson.order_matters || false,
        max_score: existingLesson.max_score,
        time_limit_seconds: existingLesson.time_limit_seconds || 60,
        max_attempts: existingLesson.max_attempts ?? undefined,
        hints: existingLesson.hints || [],
        dataset_id: existingLesson.dataset?.id ?? undefined,
        module_id: existingLesson.module ?? undefined,
        is_published: existingLesson.is_published,
      });
    }
  }, [existingLesson, reset]);

  async function onSubmit(data: LessonFormData) {
    setApiError('');
    try {
      if (isEditing) {
        await updateLessonMutation.mutateAsync(data);
      } else {
        await createLesson.mutateAsync(data);
      }
      navigate(`/courses/${courseId}/manage`);
    } catch (err) {
      setApiError(getApiErrorMessage(err, 'Failed to save lesson'));
    }
  }

  function addHint() {
    if (newHint.trim()) {
      setValue('hints', [...hints, newHint.trim()]);
      setNewHint('');
    }
  }

  function removeHint(index: number) {
    setValue('hints', hints.filter((_, i) => i !== index));
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
              <Input
                id="title"
                {...register('title')}
                placeholder="e.g., Introduction to SELECT"
              />
              {errors.title && (
                <p className="text-sm text-destructive">{errors.title.message}</p>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="description">Short Description</Label>
              <Input
                id="description"
                {...register('description')}
                placeholder="Brief description shown on the card"
              />
            </div>

            <div className="space-y-2">
              <Label>Lesson Type *</Label>
              <div className="grid gap-2 sm:grid-cols-3">
                {LESSON_TYPES.map((type) => (
                  <label
                    key={type.value}
                    className={`flex flex-col p-3 rounded-lg border cursor-pointer transition-colors ${
                      lessonType === type.value
                        ? 'border-primary bg-primary/5'
                        : 'hover:bg-muted'
                    }`}
                  >
                    <input
                      type="radio"
                      value={type.value}
                      {...register('lesson_type')}
                      className="sr-only"
                    />
                    <span className="font-medium">{type.label}</span>
                    <span className="text-xs text-muted-foreground">{type.description}</span>
                  </label>
                ))}
              </div>
            </div>

            {modules.length > 0 && (
              <div className="space-y-2">
                <Label htmlFor="module_id">Module</Label>
                <select
                  id="module_id"
                  value={watch('module_id') ?? ''}
                  onChange={(e) =>
                    setValue('module_id', e.target.value || undefined)
                  }
                  className="w-full p-2 text-sm bg-background border rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
                >
                  <option value="">No module</option>
                  {modules.map((mod) => (
                    <option key={mod.id} value={mod.id}>
                      {mod.title}
                    </option>
                  ))}
                </select>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Theory Content */}
        {showTheory && (
          <Card>
            <CardHeader>
              <CardTitle>Theory Content</CardTitle>
              <CardDescription>Educational material for this lesson</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                <Label htmlFor="theory_content">Content (Markdown supported)</Label>
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

        {/* Practice Content */}
        {showPractice && (
          <Card>
            <CardHeader>
              <CardTitle>Practice Task</CardTitle>
              <CardDescription>SQL exercise for students</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="dataset_id">Dataset</Label>
                <select
                  id="dataset_id"
                  value={watch('dataset_id') ?? ''}
                  onChange={(e) =>
                    setValue('dataset_id', e.target.value || undefined)
                  }
                  className="w-full p-2 text-sm bg-background border rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
                >
                  <option value="">No dataset</option>
                  {datasets.map((ds) => (
                    <option key={ds.id} value={ds.id}>
                      {ds.name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="practice_description">Task Description</Label>
                <textarea
                  id="practice_description"
                  {...register('practice_description')}
                  placeholder="Describe what the student needs to do..."
                  className="w-full h-24 p-3 text-sm bg-background border rounded-md resize-none focus:outline-none focus:ring-2 focus:ring-primary"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="practice_initial_code">Initial Code (optional)</Label>
                <SqlEditor
                  value={practiceInitialCode}
                  onChange={(v) => setValue('practice_initial_code', v)}
                  height="96px"
                  placeholder="-- Start writing your query here"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="expected_query">Expected Query (for grading)</Label>
                <SqlEditor
                  value={expectedQuery}
                  onChange={(v) => setValue('expected_query', v)}
                  height="96px"
                  placeholder="SELECT * FROM users WHERE active = true;"
                />
              </div>

              <div className="grid gap-4 sm:grid-cols-3">
                <div className="space-y-2">
                  <Label htmlFor="max_score">Max Score</Label>
                  <Input
                    id="max_score"
                    type="number"
                    min="1"
                    value={watch('max_score')}
                    onChange={(e) =>
                      setValue('max_score', parseInt(e.target.value) || 100)
                    }
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="time_limit_seconds">Time Limit (seconds)</Label>
                  <Input
                    id="time_limit_seconds"
                    type="number"
                    min="1"
                    value={watch('time_limit_seconds')}
                    onChange={(e) =>
                      setValue('time_limit_seconds', parseInt(e.target.value) || 60)
                    }
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="max_attempts">Max Attempts</Label>
                  <Input
                    id="max_attempts"
                    type="number"
                    min="1"
                    value={watch('max_attempts') ?? ''}
                    onChange={(e) =>
                      setValue(
                        'max_attempts',
                        e.target.value ? parseInt(e.target.value) : undefined
                      )
                    }
                    placeholder="Unlimited"
                  />
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Hints */}
        {showPractice && (
          <Card>
            <CardHeader>
              <CardTitle>Hints</CardTitle>
              <CardDescription>Help students when they're stuck</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                {hints.map((hint, index) => (
                  <div key={index} className="flex items-center gap-2 p-2 bg-muted rounded-md">
                    <span className="flex-1 text-sm">{hint}</span>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      onClick={() => removeHint(index)}
                    >
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
            </CardContent>
          </Card>
        )}

        {/* Actions */}
        <div className="flex justify-between">
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              {...register('is_published')}
              className="rounded"
            />
            <span className="text-sm">Publish immediately</span>
          </label>
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
