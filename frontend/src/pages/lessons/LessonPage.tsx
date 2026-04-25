import { useEffect, useState, useCallback, useMemo } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Spinner } from '@/components/ui/spinner';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table';
import {
  ArrowLeft,
  CheckCircle,
  XCircle,
  Play,
  Lightbulb,
  ChevronRight,
  ChevronLeft,
  BookOpen,
  Code,
  Clock,
  Paperclip,
  Download,
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import rehypeSanitize, { defaultSchema } from 'rehype-sanitize';
import { SqlExerciseBlock } from '@/components/editor/SqlExerciseBlock';
import type { Submission } from '@/types';
import type { LessonExercise } from '@/api/lessons';
import { useLesson, useLessonSubmissions, useSubmitLesson } from '@/hooks/queries/useLessons';
import { useAttachments } from '@/hooks/queries/useAttachments';
import { getApiErrorMessage } from '@/lib/utils';
import { SqlEditor } from '@/components/editor/SqlEditor';
import { useSqlite } from '@/hooks/useSqlite';
import { formatFileSize, getFileTypeIcon } from '@/components/ui/FileUpload';
import type { LocalQueryResult } from '@/lib/sqljs';

const sanitizeSchema = {
  ...defaultSchema,
  attributes: {
    ...defaultSchema.attributes,
    code: [...(defaultSchema.attributes?.code || []), 'className'],
  },
};

function formatTime(seconds: number) {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${s.toString().padStart(2, '0')}`;
}

interface ExercisePanelProps {
  exercise: LessonExercise;
  databaseType?: string;
  query: string;
  onChangeQuery: (q: string) => void;
  onSubmit: () => void;
  isSubmitting: boolean;
  submission: Submission | null;
  localResult: LocalQueryResult | null;
  canSubmit: boolean;
  attemptsLeft?: number;
  maxAttempts?: number;
}

function ExercisePanel({
  exercise,
  query,
  onChangeQuery,
  onSubmit,
  isSubmitting,
  submission,
  localResult,
  canSubmit,
  attemptsLeft,
  maxAttempts,
  databaseType,
}: ExercisePanelProps) {
  const { t } = useTranslation('lessons');
  const [showHint, setShowHint] = useState(false);
  const [hintIndex, setHintIndex] = useState(0);

  const hints = exercise.hints || [];
  const isSqlite = databaseType === 'sqlite';

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <div className="space-y-4">
        <Card>
          <CardHeader>
            <CardTitle>{exercise.title}</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="whitespace-pre-wrap">
              {exercise.description || t('page.defaultTaskDescription')}
            </p>
          </CardContent>
        </Card>

        {hints.length > 0 && (
          <Card>
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardTitle className="text-base flex items-center gap-2">
                  <Lightbulb className="h-4 w-4" />
                  {t('page.hints')}
                </CardTitle>
                <Button variant="ghost" size="sm" onClick={() => setShowHint(!showHint)}>
                  {showHint ? t('page.hide') : t('page.show')}
                </Button>
              </div>
            </CardHeader>
            {showHint && (
              <CardContent>
                <div className="flex items-center justify-between mb-2">
                  <Button variant="ghost" size="icon" disabled={hintIndex === 0} onClick={() => setHintIndex((i) => i - 1)}>
                    <ChevronLeft className="h-4 w-4" />
                  </Button>
                  <span className="text-sm text-muted-foreground">
                    {t('page.hintOf', { current: hintIndex + 1, total: hints.length })}
                  </span>
                  <Button variant="ghost" size="icon" disabled={hintIndex >= hints.length - 1} onClick={() => setHintIndex((i) => i + 1)}>
                    <ChevronRight className="h-4 w-4" />
                  </Button>
                </div>
                <p className="text-sm bg-muted p-3 rounded-md">{hints[hintIndex]}</p>
              </CardContent>
            )}
          </Card>
        )}

        {exercise.dataset && (
          <Card>
            <CardHeader>
              <CardTitle className="text-base">{t('page.databaseSchema')}</CardTitle>
              <CardDescription>{exercise.dataset.name}</CardDescription>
            </CardHeader>
            <CardContent>
              <pre className="text-xs bg-muted p-3 rounded-md overflow-auto max-h-48">
                {exercise.dataset.schema_sql}
              </pre>
            </CardContent>
          </Card>
        )}
      </div>

      <div className="space-y-4">
        <Card>
          <CardHeader>
            <CardTitle>{t('page.yourQuery')}</CardTitle>
            <CardDescription>
              {t('page.pressCtrlEnter')}
              {maxAttempts && ` • ${t('page.attemptsLeft', { count: attemptsLeft })}`}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <SqlEditor
              value={query}
              onChange={onChangeQuery}
              height="192px"
              readOnly={!canSubmit}
              onExecute={onSubmit}
              placeholder={t('page.queryPlaceholder')}
            />
            <div className="flex items-center justify-end mt-4">
              <Button onClick={onSubmit} disabled={isSubmitting || !query.trim() || !canSubmit}>
                {isSubmitting ? <Spinner size="sm" className="mr-2" /> : <Play className="h-4 w-4 mr-2" />}
                {t('page.runQuery')}
              </Button>
            </div>
          </CardContent>
        </Card>

        {isSqlite && localResult && (
          <Card>
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardTitle className="text-base">{t('page.queryOutput')}</CardTitle>
                <Badge variant="outline">{localResult.execution_time_ms}ms ({t('page.local')})</Badge>
              </div>
            </CardHeader>
            <CardContent>
              {localResult.error_message && (
                <Alert variant="destructive" className="mb-4">
                  <AlertDescription className="font-mono text-xs">{localResult.error_message}</AlertDescription>
                </Alert>
              )}
              {localResult.success && localResult.columns.length > 0 && (
                <div className="overflow-auto max-h-48 border rounded-md">
                  <Table className="w-full text-sm">
                    <TableHeader className="bg-muted sticky top-0">
                      <TableRow>
                        {localResult.columns.map((col, i) => (
                          <TableHead key={i} className="px-2 py-1 text-left font-medium border-b">{col}</TableHead>
                        ))}
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {localResult.rows.slice(0, 10).map((row, i) => (
                        <TableRow key={i} className="border-b">
                          {(row as unknown[]).map((cell, j) => (
                            <TableCell key={j} className="px-2 py-1 font-mono text-xs">
                              {cell === null ? <span className="text-muted-foreground italic">NULL</span> : String(cell)}
                            </TableCell>
                          ))}
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              )}
            </CardContent>
          </Card>
        )}

        {submission && (
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="text-base">{t('page.result')}</CardTitle>
                {submission.is_correct ? (
                  <Badge variant="success">
                    <CheckCircle className="h-3 w-3 mr-1" />
                    {t('page.correct')}
                  </Badge>
                ) : (
                  <Badge variant="destructive">
                    <XCircle className="h-3 w-3 mr-1" />
                    {t('page.incorrect')}
                  </Badge>
                )}
              </div>
            </CardHeader>
            <CardContent>
              {submission.status === 'error' && (
                <Alert variant="destructive" className="mb-4">
                  <AlertDescription>{submission.error_message}</AlertDescription>
                </Alert>
              )}
              {submission.result && (
                <div className="overflow-auto">
                  <Table className="w-full text-sm">
                    <TableHeader>
                      <TableRow className="border-b">
                        {submission.result.columns.map((col: string, i: number) => (
                          <TableHead key={i} className="px-2 py-1 text-left font-medium">{col}</TableHead>
                        ))}
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {submission.result.rows.slice(0, 10).map((row: unknown[], i: number) => (
                        <TableRow key={i} className="border-b">
                          {row.map((cell, j) => (
                            <TableCell key={j} className="px-2 py-1">{String(cell ?? 'NULL')}</TableCell>
                          ))}
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              )}
              <div className="flex items-center justify-between mt-4 text-sm text-muted-foreground">
                <span>{t('page.score', { score: submission.score, max: exercise.max_score })}</span>
                <span>{t('page.time', { ms: submission.execution_time_ms })}</span>
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}

export function LessonPage() {
  const { t } = useTranslation('lessons');
  const { courseId, lessonId } = useParams<{ courseId: string; lessonId: string }>();
  const navigate = useNavigate();

  const { data: lesson, isLoading: lessonLoading } = useLesson(courseId, lessonId);
  const { data: submissions = [], isLoading: subsLoading } = useLessonSubmissions(courseId, lessonId);
  const { data: attachments = [] } = useAttachments(courseId, lessonId);
  const submitMutation = useSubmitLesson(courseId!, lessonId!);
  const loading = lessonLoading || subsLoading;

  const exercises = useMemo<LessonExercise[]>(() => lesson?.exercises ?? [], [lesson?.exercises]);
  const [activeExerciseIdx, setActiveExerciseIdx] = useState(0);
  // Per-exercise local UI state
  const [queries, setQueries] = useState<Record<string, string>>({});
  const [submissionsByExercise, setSubmissionsByExercise] = useState<Record<string, Submission | null>>({});
  const [localResultByExercise, setLocalResultByExercise] = useState<Record<string, LocalQueryResult | null>>({});
  const [error, setError] = useState('');
  const [activeTab, setActiveTab] = useState<'theory' | 'practice'>('theory');
  const [timerStart, setTimerStart] = useState<number | null>(null);
  const [now, setNow] = useState<number>(() => Date.now());

  const sqlite = useSqlite();
  const isSqlite = lesson?.database_type === 'sqlite';

  // Initialize per-exercise queries from existing submissions or initial code
  useEffect(() => {
    if (!lesson) return;
    setQueries((prev) => {
      const updated = { ...prev };
      for (const ex of exercises) {
        if (!ex.id) continue;
        if (updated[ex.id] !== undefined) continue;
        const exerciseSub = submissions.find((s: Submission) => s.exercise === ex.id);
        updated[ex.id] = exerciseSub?.query ?? ex.initial_code ?? '';
      }
      return updated;
    });
    if (lesson.lesson_type === 'practice') {
      setActiveTab('practice');
    }
  }, [lesson, exercises, submissions]);

  // Initialize SQLite for the active exercise's dataset
  const activeExercise = exercises[activeExerciseIdx];
  useEffect(() => {
    if (lesson && isSqlite && activeExercise?.dataset) {
      sqlite.initDatabase(activeExercise.dataset.schema_sql, activeExercise.dataset.seed_sql || '');
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lesson?.id, isSqlite, activeExercise?.id, sqlite.initDatabase]);

  // Shared timer: starts on first practice tab visit
  useEffect(() => {
    if (activeTab === 'practice' && timerStart === null && lesson?.lesson_type !== 'theory') {
      setTimerStart(Date.now());
    }
  }, [activeTab, timerStart, lesson?.lesson_type]);

  useEffect(() => {
    if (timerStart === null) return;
    const interval = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(interval);
  }, [timerStart]);

  const totalSeconds = lesson?.time_limit_seconds ?? 600;
  const elapsed = timerStart ? Math.floor((now - timerStart) / 1000) : 0;
  const remaining = Math.max(totalSeconds - elapsed, 0);
  const timeUp = timerStart !== null && remaining === 0;

  const handleSubmit = useCallback(async () => {
    if (!courseId || !lessonId || !activeExercise?.id) return;
    const exId = activeExercise.id;
    const q = queries[exId] ?? '';
    if (!q.trim()) return;

    if (isSqlite && sqlite.isReady) {
      const result = sqlite.execute(q.trim());
      setLocalResultByExercise((prev) => ({ ...prev, [exId]: result }));
    }

    try {
      setError('');
      setSubmissionsByExercise((prev) => ({ ...prev, [exId]: null }));
      if (!isSqlite) {
        setLocalResultByExercise((prev) => ({ ...prev, [exId]: null }));
      }
      const sub = await submitMutation.mutateAsync({ query: q.trim(), exerciseId: exId });
      setSubmissionsByExercise((prev) => ({ ...prev, [exId]: sub }));
    } catch (err) {
      setError(getApiErrorMessage(err, t('page.failedSubmit')));
    }
  }, [courseId, lessonId, activeExercise?.id, queries, isSqlite, sqlite, submitMutation, t]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Spinner size="lg" />
      </div>
    );
  }

  if (!lesson) {
    return (
      <div className="text-center py-12">
        <h2 className="text-xl font-semibold mb-2">{t('page.lessonNotFound')}</h2>
        <Link to={`/courses/${courseId}`} className="text-primary hover:underline">
          {t('page.backToCourse')}
        </Link>
      </div>
    );
  }

  const hasPractice = lesson.lesson_type !== 'theory' && exercises.length > 0;
  const hasTheory = lesson.lesson_type !== 'practice';
  const maxAttempts = lesson.max_attempts;
  const attemptsForActive = activeExercise?.id
    ? submissions.filter((s: Submission) => s.exercise === activeExercise.id).length
    : 0;
  const attemptsLeft = maxAttempts ? maxAttempts - attemptsForActive : undefined;
  const canSubmit = !timeUp && (!maxAttempts || (attemptsLeft !== undefined && attemptsLeft > 0));

  const activeExId = activeExercise?.id;
  const activeQuery = activeExId ? queries[activeExId] ?? '' : '';
  const activeSub = activeExId ? submissionsByExercise[activeExId] ?? null : null;
  const activeLocal = activeExId ? localResultByExercise[activeExId] ?? null : null;

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" onClick={() => navigate(`/courses/${courseId}`)}>
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div className="flex-1">
          <h1 className="text-2xl font-bold">{lesson.title}</h1>
          <p className="text-muted-foreground">{lesson.course_title}</p>
        </div>
        <Badge variant="outline">
          {lesson.lesson_type === 'theory' ? (
            <>
              <BookOpen className="h-3 w-3 mr-1" />
              {t('page.theory')}
            </>
          ) : lesson.lesson_type === 'practice' ? (
            <>
              <Code className="h-3 w-3 mr-1" />
              {t('page.practice')}
            </>
          ) : (
            t('page.mixed')
          )}
        </Badge>
        {hasPractice && lesson.user_completed && (
          <Badge variant="success">
            <CheckCircle className="h-3 w-3 mr-1" />
            {t('page.completed')}
          </Badge>
        )}
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {timeUp && (
        <Alert variant="destructive">
          <AlertDescription>{t('page.timeIsUp', { defaultValue: "Time is up. You can no longer submit answers." })}</AlertDescription>
        </Alert>
      )}

      {lesson.lesson_type === 'mixed' && (
        <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as 'theory' | 'practice')}>
          <TabsList>
            <TabsTrigger value="theory">
              <BookOpen className="h-4 w-4 mr-2" />
              {t('page.theory')}
            </TabsTrigger>
            <TabsTrigger value="practice">
              <Code className="h-4 w-4 mr-2" />
              {t('page.practice')}
            </TabsTrigger>
          </TabsList>
        </Tabs>
      )}

      {hasTheory && (activeTab === 'theory' || lesson.lesson_type === 'theory') && (
        <Card>
          <CardContent className="prose prose-sm dark:prose-invert max-w-none pt-6">
            {lesson.theory_content ? (
              <ReactMarkdown
                rehypePlugins={[[rehypeSanitize, sanitizeSchema]]}
                components={{
                  code({ className, children, ...props }) {
                    if (className === 'language-sql-exercise') {
                      try {
                        const config = JSON.parse(String(children).trim());
                        return <SqlExerciseBlock config={config} />;
                      } catch {
                        return <code className={className} {...props}>{children}</code>;
                      }
                    }
                    return <code className={className} {...props}>{children}</code>;
                  },
                  pre({ children }) {
                    return <>{children}</>;
                  },
                }}
              >
                {lesson.theory_content}
              </ReactMarkdown>
            ) : (
              <p className="text-muted-foreground">{t('page.noTheoryContent')}</p>
            )}
          </CardContent>
        </Card>
      )}

      {attachments.length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base flex items-center gap-2">
              <Paperclip className="h-4 w-4" />
              {t('page.attachments', { count: attachments.length })}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {attachments.map((att) => (
                <a
                  key={att.id}
                  href={att.download_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-3 p-2 rounded-md hover:bg-muted transition-colors"
                >
                  <span>{getFileTypeIcon(att.file_type)}</span>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">{att.filename}</p>
                    <p className="text-xs text-muted-foreground">{formatFileSize(att.file_size)}</p>
                  </div>
                  <Download className="h-4 w-4 text-muted-foreground" />
                </a>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {hasPractice && (activeTab === 'practice' || lesson.lesson_type === 'practice') && (
        <div className="space-y-4">
          {/* Shared timer + exercise tabs */}
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <Clock className="h-4 w-4" />
                  <span className="font-mono text-lg">{formatTime(remaining)}</span>
                  <span className="text-xs text-muted-foreground ml-2">
                    {t('page.timeForAll', { defaultValue: 'shared across all exercises' })}
                  </span>
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                {exercises.map((ex, idx) => {
                  const sub = ex.id ? submissionsByExercise[ex.id] : null;
                  const wasCorrect =
                    submissions.find((s: Submission) => s.exercise === ex.id && s.is_correct) ||
                    sub?.is_correct;
                  return (
                    <Button
                      key={ex.id ?? idx}
                      variant={idx === activeExerciseIdx ? 'default' : 'outline'}
                      size="sm"
                      onClick={() => setActiveExerciseIdx(idx)}
                    >
                      {wasCorrect && <CheckCircle className="h-3 w-3 mr-1" />}
                      {ex.title || `Exercise ${idx + 1}`}
                    </Button>
                  );
                })}
              </div>
            </CardContent>
          </Card>

          {activeExercise && (
            <ExercisePanel
              exercise={activeExercise}
              databaseType={lesson.database_type}
              query={activeQuery}
              onChangeQuery={(q) => {
                if (activeExId) setQueries((prev) => ({ ...prev, [activeExId]: q }));
              }}
              onSubmit={handleSubmit}
              isSubmitting={submitMutation.isPending}
              submission={activeSub}
              localResult={activeLocal}
              canSubmit={canSubmit}
              attemptsLeft={attemptsLeft}
              maxAttempts={maxAttempts}
            />
          )}
        </div>
      )}
    </div>
  );
}
