import { useState } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Spinner } from '@/components/ui/spinner';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
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

export function CourseManagePage() {
  const { t } = useTranslation('instructor');
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

  // Dialog state for confirmations
  const [deleteLessonId, setDeleteLessonId] = useState<string | null>(null);
  const [deleteModuleId, setDeleteModuleId] = useState<string | null>(null);

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

  async function confirmDeleteLesson() {
    if (!deleteLessonId) return;
    try {
      await deleteLessonMutation.mutateAsync(deleteLessonId);
    } catch {
      setError('Failed to delete lesson');
    } finally {
      setDeleteLessonId(null);
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

  async function confirmDeleteModule() {
    if (!deleteModuleId) return;
    try {
      await deleteModuleMutation.mutateAsync(deleteModuleId);
    } catch {
      setError('Failed to delete module');
    } finally {
      setDeleteModuleId(null);
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
        <h2 className="text-xl font-semibold mb-2">{t('courseManage.courseNotFound')}</h2>
        <Link to="/my-courses" className="text-primary hover:underline">
          {t('courseManage.backToMyCourses')}
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" onClick={() => navigate('/my-courses')}>
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold">{course.title}</h1>
            {course.is_published ? (
              <Badge variant="default">{t('courseManage.published')}</Badge>
            ) : (
              <Badge variant="secondary">{t('courseManage.draft')}</Badge>
            )}
          </div>
          <p className="text-muted-foreground">{t('courseManage.manageContent')}</p>
        </div>
        <div className="flex gap-2">
          <Link to={`/courses/${courseId}/students`}>
            <Button variant="outline">
              <Users className="h-4 w-4 mr-2" />
              {t('courseManage.studentsCount', { count: course.student_count })}
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
            {t('courseManage.duplicate')}
          </Button>
          <Link to={`/courses/${courseId}/edit`}>
            <Button variant="outline">
              <Settings className="h-4 w-4 mr-2" />
              {t('courseManage.settings')}
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
            {course.is_published ? t('courseManage.unpublish') : t('courseManage.publish')}
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
        <Card variant="glass">
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>{t('courseManage.modules')}</CardTitle>
                <CardDescription>
                  {t('courseManage.modulesCount', { count: modules.length })}
                </CardDescription>
              </div>
              <Button
                variant="outline"
                onClick={() => setShowAddModule(!showAddModule)}
              >
                <FolderPlus className="h-4 w-4 mr-2" />
                {t('courseManage.addModule')}
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            {showAddModule && (
              <div className="flex gap-2 mb-4">
                <Input
                  placeholder={t('courseManage.moduleTitlePlaceholder')}
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
                  {t('courseManage.add')}
                </Button>
              </div>
            )}
            <div className="space-y-2">
              {modules.map((mod) => (
                <div
                  key={mod.id}
                  className="flex items-center gap-4 p-3 rounded-xl border border-border/50 hover:bg-muted/30 transition-colors"
                >
                  <div className="text-muted-foreground cursor-move">
                    <GripVertical className="h-5 w-5" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-medium truncate">{mod.title}</span>
                      <Badge variant="outline">{mod.lesson_count} {t('courseManage.lessons').toLowerCase()}</Badge>
                      {!mod.is_published && (
                        <Badge variant="secondary">{t('courseManage.draft')}</Badge>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-1">
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => toggleModulePublish(mod)}
                      title={mod.is_published ? t('courseManage.unpublish') : t('courseManage.publish')}
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
                      onClick={() => setDeleteModuleId(mod.id)}
                      title={t('courseManage.deleteModule')}
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
      <Card variant="glass">
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>{t('courseManage.lessons')}</CardTitle>
              <CardDescription>
                {t('courseManage.lessonsCount', { count: lessons.length })}
              </CardDescription>
            </div>
            <div className="flex gap-2">
              {modules.length === 0 && (
                <Button
                  variant="outline"
                  onClick={() => setShowAddModule(!showAddModule)}
                >
                  <FolderPlus className="h-4 w-4 mr-2" />
                  {t('courseManage.addModule')}
                </Button>
              )}
              <Link to={`/courses/${courseId}/lessons/new`}>
                <Button>
                  <Plus className="h-4 w-4 mr-2" />
                  {t('courseManage.addLesson')}
                </Button>
              </Link>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {modules.length === 0 && showAddModule && (
            <div className="flex gap-2 mb-4">
              <Input
                placeholder={t('courseManage.moduleTitlePlaceholder')}
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
                {t('courseManage.add')}
              </Button>
            </div>
          )}
          {lessons.length === 0 ? (
            <div className="text-center py-12">
              <Layers className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
              <h3 className="font-medium text-lg mb-2">{t('courseManage.noLessons')}</h3>
              <p className="text-muted-foreground mb-4">
                {t('courseManage.noLessonsDesc')}
              </p>
              <Link to={`/courses/${courseId}/lessons/new`}>
                <Button>
                  <Plus className="h-4 w-4 mr-2" />
                  {t('courseManage.addFirstLesson')}
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
                    className="flex items-center gap-4 p-4 rounded-xl border border-border/50 bg-card hover:bg-muted/30 transition-colors"
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
                          {t(`courseManage.${lesson.lesson_type}`)}
                        </Badge>
                        {!lesson.is_published && (
                          <Badge variant="secondary" className="shrink-0">
                            {t('courseManage.draft')}
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
                        title={lesson.is_published ? t('courseManage.unpublish') : t('courseManage.publish')}
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
                        onClick={() => setDeleteLessonId(lesson.id)}
                        title={t('courseManage.deleteLesson')}
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

      {/* Delete Lesson Dialog */}
      <Dialog open={!!deleteLessonId} onOpenChange={(open) => !open && setDeleteLessonId(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('courseManage.deleteLesson')}</DialogTitle>
            <DialogDescription>
              {t('courseManage.deleteLessonConfirm')}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteLessonId(null)}>
              {t('courseManage.cancel')}
            </Button>
            <Button variant="destructive" onClick={confirmDeleteLesson}>
              {t('courseManage.confirm')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Module Dialog */}
      <Dialog open={!!deleteModuleId} onOpenChange={(open) => !open && setDeleteModuleId(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('courseManage.deleteModule')}</DialogTitle>
            <DialogDescription>
              {t('courseManage.deleteModuleConfirm')}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteModuleId(null)}>
              {t('courseManage.cancel')}
            </Button>
            <Button variant="destructive" onClick={confirmDeleteModule}>
              {t('courseManage.confirm')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
