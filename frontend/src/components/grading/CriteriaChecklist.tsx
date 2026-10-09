import { useTranslation } from 'react-i18next';
import { CheckCircle, XCircle } from 'lucide-react';
import type { CriteriaSummary, SubmissionFeedback } from '@/types';

interface CriteriaChecklistProps {
  summary?: CriteriaSummary;
  feedback?: SubmissionFeedback;
}

/**
 * With `feedback`: the verdict list of a graded attempt ("Пройдено 6 із 7").
 * With only `summary`: what will be checked, shown before the first attempt.
 */
export function CriteriaChecklist({ summary, feedback }: CriteriaChecklistProps) {
  const { t } = useTranslation('lessons');

  if (feedback?.criteria && feedback.criteria.length > 0) {
    const passed = feedback.passed_count ?? feedback.criteria.filter((c) => c.passed).length;
    const total = feedback.total ?? feedback.criteria.length;
    const threshold = feedback.threshold ?? total;
    const ok = passed >= threshold;
    return (
      <div className="space-y-2" data-testid="criteria-result">
        <p className={`text-sm font-medium ${ok ? 'text-green-600 dark:text-green-400' : 'text-destructive'}`}>
          {t('page.criteriaPassed', { passed, total })}
          {!ok && (
            <span className="text-muted-foreground">, {t('page.criteriaNeeded', { threshold })}</span>
          )}
        </p>
        <ul className="space-y-1">
          {feedback.criteria.map((c) => (
            <li key={c.id} className="flex items-start gap-2 text-sm">
              {c.passed ? (
                <CheckCircle className="h-4 w-4 mt-0.5 shrink-0 text-green-600 dark:text-green-400" aria-label="✓" />
              ) : (
                <XCircle className="h-4 w-4 mt-0.5 shrink-0 text-destructive" aria-label="✗" />
              )}
              <span>
                {c.name}
                {!c.passed && c.detail && (
                  <span className="block text-xs text-muted-foreground">{c.detail}</span>
                )}
              </span>
            </li>
          ))}
        </ul>
      </div>
    );
  }

  if (summary && summary.criteria.length > 0) {
    return (
      <div className="space-y-1" data-testid="criteria-summary">
        <p className="text-sm font-medium">{t('page.criteriaTitle')}</p>
        <p className="text-xs text-muted-foreground">
          {t('page.criteriaCount', { total: summary.total, threshold: summary.threshold })}
        </p>
        <ul className="list-disc pl-5 text-sm">
          {summary.criteria.map((c) => (
            <li key={c.id}>{c.name}</li>
          ))}
        </ul>
      </div>
    );
  }

  return null;
}
