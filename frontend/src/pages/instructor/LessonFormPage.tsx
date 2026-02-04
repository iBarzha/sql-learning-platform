import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Spinner } from '@/components/ui/spinner';
import { ArrowLeft, Save, Plus, X } from 'lucide-react';
import lessonsApi, { type CreateLessonData } from '@/api/lessons';
import coursesApi from '@/api/courses';
import type { Dataset } from '@/types';

const LESSON_TYPES = [
  { value: 'theory', label: 'Theory', description: 'Educational content only' },
  { value: 'practice', label: 'Practice', description: 'SQL exercises only' },
  { value: 'mixed', label: 'Theory & Practice', description: 'Both content and exercises' },
];

export function LessonFormPage() {
  const { courseId, lessonId } = useParams<{ courseId: string; lessonId: string }>();
  const navigate = useNavigate();
  const isEditing = Boolean(lessonId);

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [datasets, setDatasets] = useState<Dataset[]>([]);

  const [formData, setFormData] = useState<CreateLessonData>({
    title: '',
    description: '',
    lesson_type: 'mixed',
    theory_content: '',
    practice_description: '',
    practice_initial_code: '',
    expected_query: '',
    max_score: 100,
    time_limit_seconds: 60,
    hints: [],
    dataset_id: undefined,
    is_published: false,
  });

  const [newHint, setNewHint] = useState('');

  useEffect(() => {
    loadData();
  }, [courseId, lessonId]);

  async function loadData() {
    try {
      setLoading(true);
      const datasetsData = await coursesApi.getDatasets(courseId!);
      setDatasets(datasetsData);

      if (isEditing && lessonId) {
        const lesson = await lessonsApi.get(courseId!, lessonId);
        setFormData({
          title: lesson.title,
          description: lesson.description || '',
          lesson_type: lesson.lesson_type,
          theory_content: lesson.theory_content || '',
          practice_description: lesson.practice_description || '',
          practice_initial_code: lesson.practice_initial_code || '',
          expected_query: lesson.expected_query || '',
          required_keywords: lesson.required_keywords || [],
          forbidden_keywords: lesson.forbidden_keywords || [],
          order_matters: lesson.order_matters || false,
          max_score: lesson.max_score,
          time_limit_seconds: lesson.time_limit_seconds || 60,
          max_attempts: lesson.max_attempts,
          hints: lesson.hints || [],
          dataset_id: lesson.dataset?.id,
          is_published: lesson.is_published,
        });
      }
    } catch (err) {
      setError('Failed to load data');
    } finally {
      setLoading(false);
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    setSaving(true);

    try {
      if (isEditing) {
        await lessonsApi.update(courseId!, lessonId!, formData);
      } else {
        await lessonsApi.create(courseId!, formData);
      }
      navigate(`/courses/${courseId}/manage`);
    } catch (err) {
      const message = (err as { response?: { data?: { detail?: string } } })
        ?.response?.data?.detail || 'Failed to save lesson';
      setError(message);
    } finally {
      setSaving(false);
    }
  }

  function addHint() {
    if (newHint.trim()) {
      setFormData({
        ...formData,
        hints: [...(formData.hints || []), newHint.trim()],
      });
      setNewHint('');
    }
  }

  function removeHint(index: number) {
    setFormData({
      ...formData,
      hints: formData.hints?.filter((_, i) => i !== index),
    });
  }

  const showTheory = formData.lesson_type === 'theory' || formData.lesson_type === 'mixed';
  const showPractice = formData.lesson_type === 'practice' || formData.lesson_type === 'mixed';

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

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
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
                value={formData.title}
                onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                placeholder="e.g., Introduction to SELECT"
                required
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="description">Short Description</Label>
              <Input
                id="description"
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
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
                      formData.lesson_type === type.value
                        ? 'border-primary bg-primary/5'
                        : 'hover:bg-muted'
                    }`}
                  >
                    <input
                      type="radio"
                      name="lesson_type"
                      value={type.value}
                      checked={formData.lesson_type === type.value}
                      onChange={(e) =>
                        setFormData({ ...formData, lesson_type: e.target.value as any })
                      }
                      className="sr-only"
                    />
                    <span className="font-medium">{type.label}</span>
                    <span className="text-xs text-muted-foreground">{type.description}</span>
                  </label>
                ))}
              </div>
            </div>
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
                <textarea
                  id="theory_content"
                  value={formData.theory_content}
                  onChange={(e) => setFormData({ ...formData, theory_content: e.target.value })}
                  placeholder="# Lesson Title&#10;&#10;Write your lesson content here using Markdown..."
                  className="w-full h-64 p-3 font-mono text-sm bg-background border rounded-md resize-none focus:outline-none focus:ring-2 focus:ring-primary"
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
                  value={formData.dataset_id || ''}
                  onChange={(e) =>
                    setFormData({ ...formData, dataset_id: e.target.value || undefined })
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
                  value={formData.practice_description}
                  onChange={(e) =>
                    setFormData({ ...formData, practice_description: e.target.value })
                  }
                  placeholder="Describe what the student needs to do..."
                  className="w-full h-24 p-3 text-sm bg-background border rounded-md resize-none focus:outline-none focus:ring-2 focus:ring-primary"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="practice_initial_code">Initial Code (optional)</Label>
                <textarea
                  id="practice_initial_code"
                  value={formData.practice_initial_code}
                  onChange={(e) =>
                    setFormData({ ...formData, practice_initial_code: e.target.value })
                  }
                  placeholder="-- Start writing your query here"
                  className="w-full h-24 p-3 font-mono text-sm bg-background border rounded-md resize-none focus:outline-none focus:ring-2 focus:ring-primary"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="expected_query">Expected Query (for grading)</Label>
                <textarea
                  id="expected_query"
                  value={formData.expected_query}
                  onChange={(e) => setFormData({ ...formData, expected_query: e.target.value })}
                  placeholder="SELECT * FROM users WHERE active = true;"
                  className="w-full h-24 p-3 font-mono text-sm bg-background border rounded-md resize-none focus:outline-none focus:ring-2 focus:ring-primary"
                />
              </div>

              <div className="grid gap-4 sm:grid-cols-3">
                <div className="space-y-2">
                  <Label htmlFor="max_score">Max Score</Label>
                  <Input
                    id="max_score"
                    type="number"
                    min="1"
                    value={formData.max_score}
                    onChange={(e) =>
                      setFormData({ ...formData, max_score: parseInt(e.target.value) || 100 })
                    }
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="time_limit_seconds">Time Limit (seconds)</Label>
                  <Input
                    id="time_limit_seconds"
                    type="number"
                    min="1"
                    value={formData.time_limit_seconds}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        time_limit_seconds: parseInt(e.target.value) || 60,
                      })
                    }
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="max_attempts">Max Attempts</Label>
                  <Input
                    id="max_attempts"
                    type="number"
                    min="1"
                    value={formData.max_attempts || ''}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        max_attempts: e.target.value ? parseInt(e.target.value) : undefined,
                      })
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
                {formData.hints?.map((hint, index) => (
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
              checked={formData.is_published}
              onChange={(e) => setFormData({ ...formData, is_published: e.target.checked })}
              className="rounded"
            />
            <span className="text-sm">Publish immediately</span>
          </label>
          <div className="flex gap-2">
            <Button type="button" variant="outline" onClick={() => navigate(-1)}>
              Cancel
            </Button>
            <Button type="submit" disabled={saving}>
              {saving ? <Spinner size="sm" className="mr-2" /> : <Save className="h-4 w-4 mr-2" />}
              {isEditing ? 'Save Changes' : 'Create Lesson'}
            </Button>
          </div>
        </div>
      </form>
    </div>
  );
}
