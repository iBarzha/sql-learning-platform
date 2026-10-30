import { useState, useCallback } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
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
  ClipboardCopy,
  Check,
  RefreshCw,
} from 'lucide-react';
import lessonsApi, { type Lesson } from '@/api/lessons';
import modulesApi, { type Module } from '@/api/modules';
import { useQueryClient } from '@tanstack/react-query';
import {
  useCourse,
  useUpdateCourse,
  useDuplicateCourse,
  useDeleteCourse,
} from '@/hooks/queries/useCourses';
import { useLessons, useDeleteLesson, useRegradeLesson } from '@/hooks/queries/useLessons';
import { getApiErrorMessage } from '@/lib/utils';
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
  const deleteCourseMutation = useDeleteCourse();
  const deleteLessonMutation = useDeleteLesson(courseId!);
  const regradeMutation = useRegradeLesson(courseId!);
  const createModuleMutation = useCreateModule(courseId!);
  const deleteModuleMutation = useDeleteModule(courseId!);

  const [publishing, setPublishing] = useState(false);
  const [error, setError] = useState('');

  // One dialog creates and edits modules; `id` set means editing.
  const [moduleDialog, setModuleDialog] = useState<{ id?: string } | null>(null);
  const [moduleTitle, setModuleTitle] = useState('');
  const [moduleDescription, setModuleDescription] = useState('');
  const [savingModule, setSavingModule] = useState(false);

  const [showDeleteCourse, setShowDeleteCourse] = useState(false);
  const [showDuplicate, setShowDuplicate] = useState(false);
  const [codeCopied, setCodeCopied] = useState(false);

  const [deleteLessonId, setDeleteLessonId] = useState<string | null>(null);
  const [regradeLesson, setRegradeLesson] = useState<Lesson | null>(null);
  const [deleteModuleId, setDeleteModuleId] = useState<string | null>(null);

  const handleCopyCode = useCallback(async () => {
    if (!course?.course_code) return;
    try {
      await navigator.clipboard.writeText(course.course_code);
    } catch {
      toast.error(t('courseManage.copyFailed'));
      return;
    }
    toast.success(t('courseManage.codeCopied'));
    setCodeCopied(true);
    setTimeout(() => setCodeCopied(false), 2000);
  }, [course?.course_code, t]);

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

  async function confirmRegrade() {
    if (!regradeLesson) return;
    try {
      const summary = await regradeMutation.mutateAsync(regradeLesson.id);
      const notes = [
        summary.truncated ? t('courseManage.regradeTruncated') : null,
        summary.errors > 0 ? t('courseManage.regradeErrors', { count: summary.errors }) : null,
      ].filter((note): note is string => note !== null);
      toast.success(
        t('courseManage.regradeDone', { count: summary.submissions, changed: summary.changed }),
        notes.length
          ? { description: <>{notes.map((note) => <div key={note}>{note}</div>)}</> }
          : undefined
      );
    } catch (err) {
      toast.error(getApiErrorMessage(err, t('courseManage.regradeFailed')));
    } finally {
      setRegradeLesson(null);
    }
  }

  function openModuleDialog(mod?: Module) {
    setModuleTitle(mod?.title ?? '');
    setModuleDescription(mod?.description ?? '');
    setModuleDialog({ id: mod?.id });
  }

  async function handleSaveModule() {
    const title = moduleTitle.trim();
    if (!title || !moduleDialog) return;
    try {
      setSavingModule(true);
      if (moduleDialog.id) {
        await modulesApi.update(courseId!, moduleDialog.id, {
          title,
          description: moduleDescription.trim(),
        });
        queryClient.invalidateQueries({ queryKey: ['course', courseId, 'modules'] });
      } else {
        await createModuleMutation.mutateAsync({
          title,
          description: moduleDescription.trim(),
          is_published: true,
        });
      }
      setModuleDialog(null);
    } catch {
      setError(moduleDialog.id ? 'Failed to update module' : 'Failed to create module');
    } finally {
      setSavingModule(false);
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

  async function confirmDeleteCourse() {
    try {
      await deleteCourseMutation.mutateAsync(courseId!);
      toast.success(t('courseManage.courseDeleted'));
      navigate('/my-courses');
    } catch {
      setError('Failed to delete course');
      setShowDeleteCourse(false);
    }
  }

  async function confirmDuplicate() {
    try {
      const copy = await duplicateMutation.mutateAsync({ courseId: courseId! });
      setShowDuplicate(false);
      navigate(`/courses/${copy.id}/manage`);
    } catch {
      setError('Failed to duplicate course');
      setShowDuplicate(false);
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
        <Button variant="ghost" size="icon" onClick={() => navigate('/my-courses')} aria-label={t('courseManage.backToMyCourses')}>
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
          <div className="flex items-center gap-2 mt-1">
            <p className="text-muted-foreground">{t('courseManage.manageContent')}</p>
            {course.course_code && (
              <div className="flex items-center gap-1.5 ml-2 shrink-0">
                <span className="text-xs text-muted-foreground whitespace-nowrap shrink-0">
                  {t('courseManage.courseCode')}:
                </span>
                <Badge variant="outline" className="font-mono text-sm tracking-wider px-2.5 py-0.5 shrink-0">
                  {course.course_code}
                </Badge>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-6 w-6"
                  onClick={handleCopyCode}
                  title={t('courseManage.copyCode')}
                  aria-label={t('courseManage.copyCode')}
                >
                  {codeCopied ? (
                    <Check className="h-3.5 w-3.5 text-success" />
                  ) : (
                    <ClipboardCopy className="h-3.5 w-3.5" />
                  )}
                </Button>
                {codeCopied && (
                  <span className="text-xs text-success whitespace-nowrap">{t('courseManage.codeCopied')}</span>
                )}
              </div>
            )}
          </div>
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
            onClick={() => setShowDuplicate(true)}
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
          <Button
            variant="outline"
            className="text-destructive hover:text-destructive"
            onClick={() => setShowDeleteCourse(true)}
          >
            <Trash2 className="h-4 w-4 mr-2" />
            {t('courseManage.deleteCourse')}
          </Button>
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

      {/* Modules with nested lessons */}
      <Card variant="glass">
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>{t('courseManage.modules')}</CardTitle>
              <CardDescription>
                {modules.length === 0
                  ? t('courseManage.noModulesYet')
                  : t('courseManage.modulesCount', { count: modules.length })}
              </CardDescription>
            </div>
            <Button variant="outline" onClick={() => openModuleDialog()}>
              <FolderPlus className="h-4 w-4 mr-2" />
              {t('courseManage.addModule')}
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {modules.length === 0 ? (
            <div className="text-center py-12">
              <Layers className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
              <h3 className="font-medium text-lg mb-2">{t('courseManage.noModulesTitle')}</h3>
              <p className="text-muted-foreground mb-4">
                {t('courseManage.noModulesDesc')}
              </p>
              <Button onClick={() => openModuleDialog()}>
                <FolderPlus className="h-4 w-4 mr-2" />
                {t('courseManage.addFirstModule')}
              </Button>
            </div>
          ) : (
            <div className="space-y-4">
              {modules.map((mod) => {
                const moduleLessons = lessons.filter((l) => l.module === mod.id);
                return (
                  <div
                    key={mod.id}
                    className="rounded-xl border border-border/60 bg-card/50"
                  >
                    {/* Module header */}
                    <div className="flex items-center gap-4 p-4 border-b border-border/50">
                      <div className="text-muted-foreground cursor-move">
                        <GripVertical className="h-5 w-5" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="font-semibold truncate">{mod.title}</span>
                          <Badge variant="outline">
                            {t('myCourses.lessons', { count: moduleLessons.length })}
                          </Badge>
                          {!mod.is_published && (
                            <Badge variant="secondary">{t('courseManage.draft')}</Badge>
                          )}
                        </div>
                        {mod.description && (
                          <p className="text-sm text-muted-foreground truncate">{mod.description}</p>
                        )}
                      </div>
                      <div className="flex items-center gap-1">
                        <Link to={`/courses/${courseId}/lessons/new?module=${mod.id}`}>
                          <Button variant="ghost" size="sm">
                            <Plus className="h-4 w-4 mr-1" />
                            {t('courseManage.addLesson')}
                          </Button>
                        </Link>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => openModuleDialog(mod)}
                          title={t('courseManage.editModule')}
                          aria-label={t('courseManage.editModule')}
                        >
                          <Edit className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => toggleModulePublish(mod)}
                          title={mod.is_published ? t('courseManage.unpublish') : t('courseManage.publish')}
                          aria-label={mod.is_published ? t('courseManage.unpublish') : t('courseManage.publish')}
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
                          aria-label={t('courseManage.deleteModule')}
                          className="text-destructive hover:text-destructive"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>

                    {/* Lessons inside module */}
                    {moduleLessons.length === 0 ? (
                      <div className="p-4 text-sm text-muted-foreground text-center">
                        {t('courseManage.noLessonsInModule')}
                      </div>
                    ) : (
                      <div className="p-2 space-y-1">
                        {moduleLessons.map((lesson, index) => {
                          const TypeIcon = LESSON_TYPE_ICONS[lesson.lesson_type];
                          return (
                            <div
                              key={lesson.id}
                              className="flex items-center gap-4 p-3 rounded-lg hover:bg-muted/30 transition-colors"
                            >
                              <div className="text-muted-foreground cursor-move">
                                <GripVertical className="h-4 w-4" />
                              </div>
                              <div className="flex items-center justify-center w-7 h-7 rounded-full bg-muted text-xs font-medium">
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
                                  aria-label={lesson.is_published ? t('courseManage.unpublish') : t('courseManage.publish')}
                                >
                                  {lesson.is_published ? (
                                    <Eye className="h-4 w-4" />
                                  ) : (
                                    <EyeOff className="h-4 w-4" />
                                  )}
                                </Button>
                                {lesson.lesson_type !== 'theory' && (lesson.exercise_count ?? 0) > 0 && (
                                  <Button
                                    variant="ghost"
                                    size="icon"
                                    onClick={() => setRegradeLesson(lesson)}
                                    title={t('courseManage.regrade')}
                                    aria-label={t('courseManage.regrade')}
                                  >
                                    <RefreshCw className="h-4 w-4" />
                                  </Button>
                                )}
                                <Link to={`/courses/${courseId}/lessons/${lesson.id}/edit`}>
                                  <Button variant="ghost" size="icon" title={t('courseManage.editLesson')} aria-label={t('courseManage.editLesson')}>
                                    <Edit className="h-4 w-4" />
                                  </Button>
                                </Link>
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  onClick={() => setDeleteLessonId(lesson.id)}
                                  title={t('courseManage.deleteLesson')}
                                  aria-label={t('courseManage.deleteLesson')}
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
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Create / Edit Module Dialog */}
      <Dialog open={!!moduleDialog} onOpenChange={(open) => !open && setModuleDialog(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {moduleDialog?.id ? t('courseManage.editModule') : t('courseManage.addModule')}
            </DialogTitle>
            <DialogDescription>{t('courseManage.noModulesDesc')}</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="module-title">{t('courseManage.moduleTitle')} *</Label>
              <Input
                id="module-title"
                placeholder={t('courseManage.moduleTitlePlaceholder')}
                value={moduleTitle}
                onChange={(e) => setModuleTitle(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault();
                    handleSaveModule();
                  }
                }}
                autoFocus
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="module-description">{t('courseManage.moduleDescription')}</Label>
              <Textarea
                id="module-description"
                placeholder={t('courseManage.moduleDescriptionPlaceholder')}
                value={moduleDescription}
                onChange={(e) => setModuleDescription(e.target.value)}
                rows={3}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setModuleDialog(null)}>
              {t('courseManage.cancel')}
            </Button>
            <Button onClick={handleSaveModule} disabled={!moduleTitle.trim() || savingModule}>
              {savingModule && <Spinner size="sm" className="mr-2" />}
              {moduleDialog?.id ? t('courseManage.save') : t('courseManage.add')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

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

      {/* Regrade Lesson Dialog */}
      <Dialog open={!!regradeLesson} onOpenChange={(open) => !open && !regradeMutation.isPending && setRegradeLesson(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('courseManage.regradeConfirmTitle', { title: regradeLesson?.title })}</DialogTitle>
            <DialogDescription>{t('courseManage.regradeConfirm')}</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setRegradeLesson(null)} disabled={regradeMutation.isPending}>
              {t('courseManage.cancel')}
            </Button>
            <Button onClick={confirmRegrade} disabled={regradeMutation.isPending}>
              {regradeMutation.isPending && <Spinner size="sm" className="mr-2" />}
              {t('courseManage.regrade')}
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

      {/* Duplicate Course Dialog */}
      <Dialog open={showDuplicate} onOpenChange={(open) => !open && setShowDuplicate(false)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('courseManage.duplicateConfirmTitle')}</DialogTitle>
            <DialogDescription>
              {t('courseManage.duplicateConfirm', { title: course.title })}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowDuplicate(false)}>
              {t('courseManage.cancel')}
            </Button>
            <Button onClick={confirmDuplicate} disabled={duplicateMutation.isPending}>
              {duplicateMutation.isPending && <Spinner size="sm" className="mr-2" />}
              {t('courseManage.duplicate')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Course Dialog */}
      <Dialog open={showDeleteCourse} onOpenChange={(open) => !open && setShowDeleteCourse(false)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('courseManage.deleteCourseConfirm', { title: course.title })}</DialogTitle>
            <DialogDescription>{t('courseManage.deleteCourseWarning')}</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowDeleteCourse(false)}>
              {t('courseManage.cancel')}
            </Button>
            <Button
              variant="destructive"
              onClick={confirmDeleteCourse}
              disabled={deleteCourseMutation.isPending}
            >
              {deleteCourseMutation.isPending && <Spinner size="sm" className="mr-2" />}
              {t('courseManage.deleteCourse')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
