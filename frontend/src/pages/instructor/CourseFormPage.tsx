import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Spinner } from '@/components/ui/spinner';
import { ArrowLeft, Save } from 'lucide-react';
import coursesApi, { type CreateCourseData } from '@/api/courses';

const DATABASE_TYPES = [
  { value: 'postgresql', label: 'PostgreSQL' },
  { value: 'mysql', label: 'MySQL' },
  { value: 'mariadb', label: 'MariaDB' },
  { value: 'mongodb', label: 'MongoDB' },
  { value: 'redis', label: 'Redis' },
];

export function CourseFormPage() {
  const { courseId } = useParams<{ courseId: string }>();
  const navigate = useNavigate();
  const isEditing = Boolean(courseId);

  const [loading, setLoading] = useState(isEditing);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const [formData, setFormData] = useState<CreateCourseData>({
    title: '',
    description: '',
    database_type: 'postgresql',
    enrollment_key: '',
    max_students: undefined,
    start_date: '',
    end_date: '',
  });

  useEffect(() => {
    if (isEditing && courseId) {
      loadCourse();
    }
  }, [courseId, isEditing]);

  async function loadCourse() {
    try {
      const course = await coursesApi.get(courseId!);
      setFormData({
        title: course.title,
        description: course.description,
        database_type: course.database_type,
        enrollment_key: course.enrollment_key || '',
        max_students: course.max_students,
        start_date: course.start_date || '',
        end_date: course.end_date || '',
      });
    } catch (err) {
      setError('Failed to load course');
    } finally {
      setLoading(false);
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    setSaving(true);

    try {
      const data = {
        ...formData,
        enrollment_key: formData.enrollment_key || undefined,
        max_students: formData.max_students || undefined,
        start_date: formData.start_date || undefined,
        end_date: formData.end_date || undefined,
      };

      if (isEditing) {
        await coursesApi.update(courseId!, data);
        navigate(`/courses/${courseId}/manage`);
      } else {
        const course = await coursesApi.create(data);
        navigate(`/courses/${course.id}/manage`);
      }
    } catch (err) {
      const message = (err as { response?: { data?: { detail?: string } } })
        ?.response?.data?.detail || 'Failed to save course';
      setError(message);
    } finally {
      setSaving(false);
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
            {isEditing ? 'Edit Course' : 'Create Course'}
          </h1>
          <p className="text-muted-foreground">
            {isEditing ? 'Update course details' : 'Set up a new course'}
          </p>
        </div>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <form onSubmit={handleSubmit}>
        <Card>
          <CardHeader>
            <CardTitle>Course Details</CardTitle>
            <CardDescription>Basic information about your course</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="title">Title *</Label>
              <Input
                id="title"
                value={formData.title}
                onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                placeholder="e.g., Introduction to SQL"
                required
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="description">Description</Label>
              <textarea
                id="description"
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                placeholder="What will students learn in this course?"
                className="w-full h-24 p-3 text-sm bg-background border rounded-md resize-none focus:outline-none focus:ring-2 focus:ring-primary"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="database_type">Database Type *</Label>
              <select
                id="database_type"
                value={formData.database_type}
                onChange={(e) => setFormData({ ...formData, database_type: e.target.value })}
                className="w-full p-2 text-sm bg-background border rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
              >
                {DATABASE_TYPES.map((type) => (
                  <option key={type.value} value={type.value}>
                    {type.label}
                  </option>
                ))}
              </select>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="start_date">Start Date</Label>
                <Input
                  id="start_date"
                  type="date"
                  value={formData.start_date}
                  onChange={(e) => setFormData({ ...formData, start_date: e.target.value })}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="end_date">End Date</Label>
                <Input
                  id="end_date"
                  type="date"
                  value={formData.end_date}
                  onChange={(e) => setFormData({ ...formData, end_date: e.target.value })}
                />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="mt-4">
          <CardHeader>
            <CardTitle>Enrollment Settings</CardTitle>
            <CardDescription>Control who can join your course</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="enrollment_key">Enrollment Key</Label>
              <Input
                id="enrollment_key"
                value={formData.enrollment_key}
                onChange={(e) => setFormData({ ...formData, enrollment_key: e.target.value })}
                placeholder="Leave empty for open enrollment"
              />
              <p className="text-xs text-muted-foreground">
                Students will need this key to enroll in your course
              </p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="max_students">Maximum Students</Label>
              <Input
                id="max_students"
                type="number"
                min="1"
                value={formData.max_students || ''}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    max_students: e.target.value ? parseInt(e.target.value) : undefined,
                  })
                }
                placeholder="Unlimited"
              />
            </div>
          </CardContent>
        </Card>

        <div className="flex justify-end gap-2 mt-6">
          <Button type="button" variant="outline" onClick={() => navigate(-1)}>
            Cancel
          </Button>
          <Button type="submit" disabled={saving}>
            {saving ? <Spinner size="sm" className="mr-2" /> : <Save className="h-4 w-4 mr-2" />}
            {isEditing ? 'Save Changes' : 'Create Course'}
          </Button>
        </div>
      </form>
    </div>
  );
}
