import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Spinner } from '@/components/ui/spinner';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { useStudentTimers, useTimerAction } from '@/hooks/queries/useCourses';
import { getApiErrorMessage } from '@/lib/utils';
import type { StudentTimer } from '@/types';

const MIN_MINUTES = 1;
const MAX_MINUTES = 180;
const DEFAULT_MINUTES = '10';

interface StudentTimersDialogProps {
  courseId: string;
  studentId: string;
  studentName: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

function parseMinutes(value: string): number | null {
  const minutes = Number(value);
  return Number.isInteger(minutes) && minutes >= MIN_MINUTES && minutes <= MAX_MINUTES ? minutes : null;
}

/** Timed lessons of one student: when the clock started, the deadline, and controls to reset or extend it. */
export function StudentTimersDialog({ courseId, studentId, studentName, open, onOpenChange }: StudentTimersDialogProps) {
  const { t } = useTranslation('instructor');
  const { data: timers = [], isLoading } = useStudentTimers(courseId, studentId);
  const timerAction = useTimerAction(courseId);
  const [minutesByLesson, setMinutesByLesson] = useState<Record<string, string>>({});
  const [resetTarget, setResetTarget] = useState<StudentTimer | null>(null);

  async function extend(timer: StudentTimer) {
    const minutes = parseMinutes(minutesByLesson[timer.lesson_id] ?? DEFAULT_MINUTES);
    if (minutes === null) return;
    try {
      await timerAction.mutateAsync({
        lessonId: timer.lesson_id,
        data: { student: studentId, action: 'extend', minutes },
      });
      toast.success(t('students.timers.extended', { count: minutes, lesson: timer.lesson_title }));
    } catch (err) {
      toast.error(getApiErrorMessage(err, t('students.timers.actionFailed')));
    }
  }

  async function confirmReset() {
    if (!resetTarget) return;
    try {
      await timerAction.mutateAsync({
        lessonId: resetTarget.lesson_id,
        data: { student: studentId, action: 'reset' },
      });
      toast.success(t('students.timers.resetDone', { lesson: resetTarget.lesson_title }));
    } catch (err) {
      toast.error(getApiErrorMessage(err, t('students.timers.actionFailed')));
    } finally {
      setResetTarget(null);
    }
  }

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>{t('students.timers.title')}</DialogTitle>
            <DialogDescription>{studentName}</DialogDescription>
          </DialogHeader>
          {isLoading ? (
            <div className="flex justify-center py-6">
              <Spinner size="sm" />
            </div>
          ) : (
            <div className="space-y-3 max-h-[60vh] overflow-y-auto">
              {timers.map((timer) => {
                const minutesValue = minutesByLesson[timer.lesson_id] ?? DEFAULT_MINUTES;
                return (
                  <div key={timer.lesson_id} className="rounded-lg border p-3 space-y-2">
                    <div className="flex items-center justify-between gap-2">
                      <p className="font-medium">{timer.lesson_title}</p>
                      <span className="text-xs text-muted-foreground shrink-0">
                        {t('students.timers.limit', { count: Math.round(timer.time_limit_seconds / 60) })}
                      </span>
                    </div>
                    {timer.started_at ? (
                      <div className="grid gap-1 text-sm text-muted-foreground sm:grid-cols-2">
                        <span>{t('students.timers.startedAt', { time: new Date(timer.started_at).toLocaleString() })}</span>
                        {timer.deadline && (
                          <span>{t('students.timers.deadline', { time: new Date(timer.deadline).toLocaleString() })}</span>
                        )}
                        {timer.remaining_seconds !== null && (
                          <span>
                            {timer.remaining_seconds > 0
                              ? t('students.timers.remaining', { count: Math.ceil(timer.remaining_seconds / 60) })
                              : t('students.timers.expired')}
                          </span>
                        )}
                      </div>
                    ) : (
                      <p className="text-sm text-muted-foreground">{t('students.timers.notStarted')}</p>
                    )}
                    {timer.extra_seconds > 0 && (
                      <p className="text-sm">
                        {t('students.timers.extra', { count: Math.round(timer.extra_seconds / 60) })}
                      </p>
                    )}
                    <div className="flex flex-wrap items-center gap-2">
                      <Input
                        type="number"
                        min={MIN_MINUTES}
                        max={MAX_MINUTES}
                        className="w-24"
                        aria-label={t('students.timers.minutesLabel')}
                        value={minutesValue}
                        onChange={(e) =>
                          setMinutesByLesson((prev) => ({ ...prev, [timer.lesson_id]: e.target.value }))
                        }
                      />
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        disabled={timerAction.isPending || parseMinutes(minutesValue) === null}
                        onClick={() => extend(timer)}
                      >
                        {t('students.timers.addMinutes')}
                      </Button>
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        className="text-destructive hover:text-destructive"
                        disabled={timerAction.isPending}
                        onClick={() => setResetTarget(timer)}
                      >
                        {t('students.timers.reset')}
                      </Button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </DialogContent>
      </Dialog>

      <Dialog
        open={!!resetTarget}
        onOpenChange={(isOpen) => !isOpen && !timerAction.isPending && setResetTarget(null)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('students.timers.resetConfirmTitle')}</DialogTitle>
            <DialogDescription>
              {t('students.timers.resetConfirm', { lesson: resetTarget?.lesson_title, student: studentName })}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setResetTarget(null)} disabled={timerAction.isPending}>
              {t('courseManage.cancel')}
            </Button>
            <Button variant="destructive" onClick={confirmReset} disabled={timerAction.isPending}>
              {timerAction.isPending && <Spinner size="sm" className="mr-2" />}
              {t('students.timers.reset')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
