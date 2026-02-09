import { useState } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Spinner } from '@/components/ui/spinner';
import {
  ArrowLeft,
  Plus,
  Settings,
  Eye,
  EyeOff,
  Trash2,
  GripVertical,
  BookOpen,
  Code,
  Layers,
  Edit,
  Users,
  FolderPlus,
  Copy,
} from 'lucide-react';
import lessonsApi, { type Lesson } from '@/api/lessons';
import modulesApi from '@/api/modules';
import { useQueryClient } from '@tanstack/react-query';
import { useCourse, useUpdateCourse, useDuplicateCourse } from '@/hooks/queries/useCourses';
import { useLessons, useDeleteLesson } from '@/hooks/queries/useLessons';
import { useModules, useCreateModule, useDeleteModule } from '@/hooks/queries/useModules';

const LESSON_TYPE_ICONS = {
  theory: BookOpen,
  practice: Code,
  mixed: Layers,
};

const LESSON_TYPE_LABELS = {
  theory: 'Theory',
  practice: 'Practice',
  mixed: 'Mixed',
};

export function CourseManagePage() {
  const { courseId } = useParams<{ courseId: string }>();
  const navigate = useNavigate();

  const { data: course, isLoading: courseLoading } = useCourse(courseId);
  const { data: lessonsData, isLoading: lessonsLoading } = useLessons(courseId);
  const { data: modules = [], isLoading: modulesLoading } = useModules(courseId);
  const lessons = lessonsData?.results ?? [];
  const loading = courseLoading || lessonsLoading || modulesLoading;

  const queryClient = useQueryClient();
  const updateCourse = useUpdateCourse(courseId!);
  const duplicateMutation = useDuplicateCourse();
  const deleteLessonMutation = useDeleteLesson(courseId!);
  const createModuleMutation = useCreateModule(courseId!);
  const deleteModuleMutation = useDeleteModule(courseId!);

  const [publishing, setPublishing] = useState(false);
  const [error, setError] = useState('');
  const [newModuleTitle, setNewModuleTitle] = useState('');
  const [showAddModule, setShowAddModule] = useState(false);

  async function togglePublish() {
    if (!course) return;
    try {
      setPublishing(true);
      await updateCourse.mutateAsync({ is_published: !course.is_published });
    } catch {
      setError('Failed to update course');
    } finally {
      setPublishing(false);
    }
  }

  async function toggleLessonPublish(lesson: Lesson) {
    try {
      await lessonsApi.update(courseId!, lesson.id, { is_published: !lesson.is_published });
      queryClient.invalidateQueries({ queryKey: ['course', courseId, 'lessons'] });
    } catch {
      setError('Failed to update lesson');
    }
  }

  async function deleteLesson(lessonId: string) {
    if (!confirm('Are you sure you want to delete this lesson?')) return;
    try {
      await deleteLessonMutation.mutateAsync(lessonId);
    } catch {
      setError('Failed to delete lesson');
    }
  }

  async function handleAddModule() {
    if (!newModuleTitle.trim()) return;
    try {
      await createModuleMutation.mutateAsync({
        title: newModuleTitle.trim(),
        is_published: true,
      });
      setNewModuleTitle('');
      setShowAddModule(false);
    } catch {
      setError('Failed to create module');
    }
  }

  async function handleDeleteModule(moduleId: string) {
    if (!confirm('Delete this module? Lessons will be moved to uncategorized.')) return;
    try {
      await deleteModuleMutation.mutateAsync(moduleId);
    } catch {
      setError('Failed to delete module');
    }
  }

  async function toggleModulePublish(mod: { id: string; is_published: boolean }) {
    try {
      await modulesApi.update(courseId!, mod.id, { is_published: !mod.is_published });
      queryClient.invalidateQueries({ queryKey: ['course', courseId, 'modules'] });
    } catch {
      setError('Failed to update module');
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Spinner size="lg" />
      </div>
    );
  }

  if (!course) {
    return (
      <div className="text-center py-12">
        <h2 className="text-xl font-semibold mb-2">Course not found</h2>
        <Link to="/my-courses" className="text-primary hover:underline">
          Back to my courses
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" onClick={() => navigate('/my-courses')}>
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold">{course.title}</h1>
            {course.is_published ? (
              <Badge variant="default">Published</Badge>
            ) : (
              <Badge variant="secondary">Draft</Badge>
            )}
          </div>
          <p className="text-muted-foreground">Manage course content and settings</p>
        </div>
        <div className="flex gap-2">
          <Link to={`/courses/${courseId}/students`}>
            <Button variant="outline">
              <Users className="h-4 w-4 mr-2" />
              Students ({course.student_count})
            </Button>
          </Link>
          <Button
            variant="outline"
            disabled={duplicateMutation.isPending}
            onClick={() => {
              duplicateMutation.mutate(
                { courseId: courseId! },
                { onSuccess: (newCourse) => navigate(`/courses/${newCourse.id}/manage`) }
              );
            }}
          >
            <Copy className="h-4 w-4 mr-2" />
            Duplicate
          </Button>
          <Link to={`/courses/${courseId}/edit`}>
            <Button variant="outline">
              <Settings className="h-4 w-4 mr-2" />
              Settings
            </Button>
          </Link>
          <Button onClick={togglePublish} disabled={publishing}>
            {publishing ? (
              <Spinner size="sm" className="mr-2" />
            ) : course.is_published ? (
              <EyeOff className="h-4 w-4 mr-2" />
            ) : (
              <Eye className="h-4 w-4 mr-2" />
            )}
            {course.is_published ? 'Unpublish' : 'Publish'}
          </Button>
        </div>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* Modules */}
      {modules.length > 0 && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>Modules</CardTitle>
                <CardDescription>
                  {modules.length} modules in this course
                </CardDescription>
              </div>
              <Button
                variant="outline"
                onClick={() => setShowAddModule(!showAddModule)}
              >
                <FolderPlus className="h-4 w-4 mr-2" />
                Add Module
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            {showAddModule && (
              <div className="flex gap-2 mb-4">
                <Input
                  placeholder="Module title..."
                  value={newModuleTitle}
                  onChange={(e) => setNewModuleTitle(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault();
                      handleAddModule();
                    }
                  }}
                />
                <Button onClick={handleAddModule} disabled={!newModuleTitle.trim()}>
                  Add
                </Button>
              </div>
            )}
            <div className="space-y-2">
              {modules.map((mod) => (
                <div
                  key={mod.id}
                  className="flex items-center gap-4 p-3 rounded-lg border"
                >
                  <div className="text-muted-foreground cursor-move">
                    <GripVertical className="h-5 w-5" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-medium truncate">{mod.title}</span>
                      <Badge variant="outline">{mod.lesson_count} lessons</Badge>
                      {!mod.is_published && (
                        <Badge variant="secondary">Draft</Badge>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-1">
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => toggleModulePublish(mod)}
                      title={mod.is_published ? 'Unpublish' : 'Publish'}
                    >
                      {mod.is_published ? (
                        <Eye className="h-4 w-4" />
                      ) : (
                        <EyeOff className="h-4 w-4" />
                      )}
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => handleDeleteModule(mod.id)}
                      title="Delete"
                      className="text-destructive hover:text-destructive"
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Lessons */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Lessons</CardTitle>
              <CardDescription>
                {lessons.length} lessons in this course
              </CardDescription>
            </div>
            <div className="flex gap-2">
              {modules.length === 0 && (
                <Button
                  variant="outline"
                  onClick={() => setShowAddModule(!showAddModule)}
                >
                  <FolderPlus className="h-4 w-4 mr-2" />
                  Add Module
                </Button>
              )}
              <Link to={`/courses/${courseId}/lessons/new`}>
                <Button>
                  <Plus className="h-4 w-4 mr-2" />
                  Add Lesson
                </Button>
              </Link>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {modules.length === 0 && showAddModule && (
            <div className="flex gap-2 mb-4">
              <Input
                placeholder="Module title..."
                value={newModuleTitle}
                onChange={(e) => setNewModuleTitle(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault();
                    handleAddModule();
                  }
                }}
              />
              <Button onClick={handleAddModule} disabled={!newModuleTitle.trim()}>
                Add
              </Button>
            </div>
          )}
          {lessons.length === 0 ? (
            <div className="text-center py-12">
              <Layers className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
              <h3 className="font-medium text-lg mb-2">No lessons yet</h3>
              <p className="text-muted-foreground mb-4">
                Start building your course by adding lessons
              </p>
              <Link to={`/courses/${courseId}/lessons/new`}>
                <Button>
                  <Plus className="h-4 w-4 mr-2" />
                  Add First Lesson
                </Button>
              </Link>
            </div>
          ) : (
            <div className="space-y-2">
              {lessons.map((lesson, index) => {
                const TypeIcon = LESSON_TYPE_ICONS[lesson.lesson_type];
                return (
                  <div
                    key={lesson.id}
                    className="flex items-center gap-4 p-4 rounded-lg border bg-card hover:bg-muted/50 transition-colors"
                  >
                    <div className="text-muted-foreground cursor-move">
                      <GripVertical className="h-5 w-5" />
                    </div>
                    <div className="flex items-center justify-center w-8 h-8 rounded-full bg-muted text-sm font-medium">
                      {index + 1}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <h3 className="font-medium truncate">{lesson.title}</h3>
                        <Badge variant="outline" className="shrink-0">
                          <TypeIcon className="h-3 w-3 mr-1" />
                          {LESSON_TYPE_LABELS[lesson.lesson_type]}
                        </Badge>
                        {!lesson.is_published && (
                          <Badge variant="secondary" className="shrink-0">
                            Draft
                          </Badge>
                        )}
                      </div>
                      {lesson.description && (
                        <p className="text-sm text-muted-foreground truncate">
                          {lesson.description}
                        </p>
                      )}
                    </div>
                    <div className="flex items-center gap-1">
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => toggleLessonPublish(lesson)}
                        title={lesson.is_published ? 'Unpublish' : 'Publish'}
                      >
                        {lesson.is_published ? (
                          <Eye className="h-4 w-4" />
                        ) : (
                          <EyeOff className="h-4 w-4" />
                        )}
                      </Button>
                      <Link to={`/courses/${courseId}/lessons/${lesson.id}/edit`}>
                        <Button variant="ghost" size="icon" title="Edit">
                          <Edit className="h-4 w-4" />
                        </Button>
                      </Link>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => deleteLesson(lesson.id)}
                        title="Delete"
                        className="text-destructive hover:text-destructive"
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
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
