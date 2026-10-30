import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Spinner } from '@/components/ui/spinner';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { useSetManualScore, useStudentResults } from '@/hooks/queries/useSubmissions';
import { getApiErrorMessage } from '@/lib/utils';
import type { ManualScoreData, StudentResult } from '@/types';

interface StudentResultsDialogProps {
  courseId: string;
  studentId: string;
  studentName: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

interface ResultGroup {
  key: string;
  title: string;
  results: StudentResult[];
}

/** Lesson exercises grouped by lesson (in the order the API returns them), assignments last. */
function groupResults(results: StudentResult[], assignmentsTitle: string): ResultGroup[] {
  const groups = new Map<string, ResultGroup>();
  const assignments: StudentResult[] = [];
  for (const result of results) {
    if (result.assignment) {
      assignments.push(result);
    } else if (result.lesson && result.exercise) {
      // Lesson-level rows (no exercise) only carry the timer; they are not graded tasks.
      const group = groups.get(result.lesson) ?? {
        key: result.lesson,
        title: result.lesson_title ?? '',
        results: [],
      };
      group.results.push(result);
      groups.set(result.lesson, group);
    }
  }
  const all = [...groups.values()];
  if (assignments.length > 0) {
    all.push({ key: 'assignments', title: assignmentsTitle, results: assignments });
  }
  return all;
}

function ResultRow({ result }: { result: StudentResult }) {
  const { t } = useTranslation('instructor');
  const setManualScore = useSetManualScore();
  const [score, setScore] = useState(result.manual_score === null ? '' : String(Number(result.manual_score)));
  const [comment, setComment] = useState(result.manual_comment ?? '');

  const parsedScore = score.trim() === '' ? null : Number(score);
  const scoreValid = parsedScore !== null && parsedScore >= 0 && parsedScore <= result.max_score;

  async function save(data: ManualScoreData) {
    try {
      const saved = await setManualScore.mutateAsync({ resultId: result.id, data });
      setScore(saved.manual_score === null ? '' : String(Number(saved.manual_score)));
      setComment(saved.manual_comment ?? '');
      toast.success(t('students.results.saved'));
    } catch (err) {
      toast.error(getApiErrorMessage(err, t('students.results.saveFailed')));
    }
  }

  return (
    <div className="rounded-lg border p-3 space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        <p className="font-medium flex-1 min-w-0">{result.exercise_title ?? result.assignment_title}</p>
        <span className="text-sm">
          {t('students.results.best', { score: result.best_score, max: result.max_score })}
        </span>
        <span className="text-sm text-muted-foreground">
          {t('students.results.attempts', { count: result.total_attempts })}
        </span>
        {result.is_completed ? (
          <Badge variant="success">{t('students.results.completed')}</Badge>
        ) : (
          <Badge variant="outline">{t('students.results.notCompleted')}</Badge>
        )}
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <Input
          type="number"
          min={0}
          max={result.max_score}
          step="any"
          className="w-28"
          placeholder={t('students.results.manualScore')}
          aria-label={t('students.results.manualScore')}
          value={score}
          onChange={(e) => setScore(e.target.value)}
        />
        <Input
          className="flex-1 min-w-[12rem]"
          placeholder={t('students.results.comment')}
          aria-label={t('students.results.comment')}
          value={comment}
          onChange={(e) => setComment(e.target.value)}
        />
        <Button
          type="button"
          size="sm"
          disabled={setManualScore.isPending || !scoreValid}
          onClick={() => save({ manual_score: parsedScore, manual_comment: comment.trim() })}
        >
          {t('students.results.save')}
        </Button>
        {(result.manual_score !== null || result.manual_comment) && (
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={setManualScore.isPending}
            onClick={() => save({ manual_score: null, manual_comment: '' })}
          >
            {t('students.results.reset')}
          </Button>
        )}
      </div>
      {score.trim() !== '' && !scoreValid && (
        <p className="text-xs text-destructive">
          {t('students.results.scoreRange', { max: result.max_score })}
        </p>
      )}
    </div>
  );
}

/** Every graded task of one student in the course, with a manual score override per task. */
export function StudentResultsDialog({ courseId, studentId, studentName, open, onOpenChange }: StudentResultsDialogProps) {
  const { t } = useTranslation('instructor');
  const { data: results = [], isLoading } = useStudentResults(
    open ? courseId : undefined,
    open ? studentId : undefined
  );
  const groups = groupResults(results, t('students.results.assignments'));

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl">
        <DialogHeader>
          <DialogTitle>{t('students.results.title')}</DialogTitle>
          <DialogDescription>{studentName}</DialogDescription>
        </DialogHeader>
        {isLoading ? (
          <div className="flex justify-center py-6">
            <Spinner size="sm" />
          </div>
        ) : groups.length === 0 ? (
          <p className="text-sm text-muted-foreground py-4">{t('students.results.empty')}</p>
        ) : (
          <div className="space-y-4 max-h-[65vh] overflow-y-auto">
            {groups.map((group) => (
              <div key={group.key} className="space-y-2">
                <h4 className="text-sm font-semibold">{group.title}</h4>
                {group.results.map((result) => (
                  <ResultRow key={result.id} result={result} />
                ))}
              </div>
            ))}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
