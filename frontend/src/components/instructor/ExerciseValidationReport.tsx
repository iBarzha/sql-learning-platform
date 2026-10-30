import { useTranslation } from 'react-i18next';
import { AlertTriangle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import type { LessonValidation } from '@/api/lessons';

interface ExerciseValidationReportProps {
  validation: LessonValidation;
  onHide: () => void;
}

/** Result of the dataset check for the saved lesson: caught mistakes, warnings, survivors. */
export function ExerciseValidationReport({ validation, onHide }: ExerciseValidationReportProps) {
  const { t } = useTranslation('instructor');

  return (
    <div className="space-y-3 border rounded-md p-3">
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium">{t('lessonForm.validation.title')}</p>
        <Button type="button" variant="ghost" size="sm" onClick={onHide}>
          {t('lessonForm.validation.hide')}
        </Button>
      </div>
      {validation.exercises.map((ex) => (
        <div key={ex.exercise_id} className="space-y-1 text-sm">
          <p className="font-medium">{ex.title}</p>
          {ex.skipped && (
            <p className="text-muted-foreground">{t('lessonForm.validation.skipped')}</p>
          )}
          {ex.error && <p className="text-destructive">{ex.error}</p>}
          {ex.mutants_total !== undefined && (
            <p className={ex.surviving && ex.surviving.length > 0 ? 'text-warning' : 'text-success'}>
              {t('lessonForm.validation.caught', { killed: ex.killed, total: ex.checked ?? ex.mutants_total, datasets: ex.datasets?.length ?? 1 })}
              {ex.truncated && t('lessonForm.validation.truncated', { checked: ex.checked, total: ex.mutants_total })}
            </p>
          )}
          {ex.reference_empty_on && ex.reference_empty_on.length > 0 && (
            <p className="text-muted-foreground">
              {t('lessonForm.validation.referenceEmpty', { names: ex.reference_empty_on.join(', ') })}
            </p>
          )}
          {ex.warnings && ex.warnings.length > 0 && (
            <ul className="space-y-1" aria-label={t('lessonForm.validation.warnings')}>
              {ex.warnings.map((warning, i) => (
                <li key={i} className="flex items-start gap-2 text-warning">
                  <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" aria-hidden="true" />
                  <span>{warning}</span>
                </li>
              ))}
            </ul>
          )}
          {ex.surviving && ex.surviving.length > 0 && (
            <ul className="list-disc pl-5 space-y-1">
              {ex.surviving.map((m, i) => (
                <li key={i}>
                  <span>{m.description}</span>
                  <code className="block text-xs bg-muted rounded px-2 py-1 mt-1 whitespace-pre-wrap">
                    {m.sql}
                  </code>
                </li>
              ))}
            </ul>
          )}
        </div>
      ))}
    </div>
  );
}
