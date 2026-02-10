import { useEffect, useState, useCallback } from 'react';
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
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { SqlExerciseBlock } from '@/components/editor/SqlExerciseBlock';
import type { Submission } from '@/types';
import { useLesson, useLessonSubmissions, useSubmitLesson } from '@/hooks/queries/useLessons';
import { useAttachments } from '@/hooks/queries/useAttachments';
import { getApiErrorMessage } from '@/lib/utils';
import { SqlEditor } from '@/components/editor/SqlEditor';
import { useSqlite } from '@/hooks/useSqlite';
import { formatFileSize, getFileTypeIcon } from '@/components/ui/FileUpload';
import type { LocalQueryResult } from '@/lib/sqljs';
import { Paperclip, Download } from 'lucide-react';

export function LessonPage() {
  const { t } = useTranslation('lessons');
  const { courseId, lessonId } = useParams<{ courseId: string; lessonId: string }>();
  const navigate = useNavigate();

  const { data: lesson, isLoading: lessonLoading } = useLesson(courseId, lessonId);
  const { data: submissions = [], isLoading: subsLoading } = useLessonSubmissions(courseId, lessonId);
  const { data: attachments = [] } = useAttachments(courseId, lessonId);
  const submitMutation = useSubmitLesson(courseId!, lessonId!);
  const loading = lessonLoading || subsLoading;

  const [query, setQuery] = useState('');
  const [queryInitialized, setQueryInitialized] = useState(false);
  const [currentSubmission, setCurrentSubmission] = useState<Submission | null>(null);
  const [localResult, setLocalResult] = useState<LocalQueryResult | null>(null);
  const [showHint, setShowHint] = useState(false);
  const [hintIndex, setHintIndex] = useState(0);
  const [error, setError] = useState('');
  const [activeTab, setActiveTab] = useState<'theory' | 'practice'>('theory');

  // Client-side SQLite for instant preview
  const sqlite = useSqlite();

  // Set initial query from submissions or lesson initial code
  useEffect(() => {
    if (!queryInitialized && !loading && lesson) {
      if (submissions.length > 0) {
        setQuery(submissions[0].query);
      } else if (lesson.practice_initial_code) {
        setQuery(lesson.practice_initial_code);
      }
      if (lesson.lesson_type === 'practice') {
        setActiveTab('practice');
      }
      setQueryInitialized(true);
    }
  }, [loading, lesson, submissions, queryInitialized]);

  // Initialize local SQLite DB for SQLite courses
  const isSqlite = lesson?.database_type === 'sqlite';
  useEffect(() => {
    if (lesson && isSqlite && lesson.dataset) {
      sqlite.initDatabase(lesson.dataset.schema_sql, lesson.dataset.seed_sql);
    }
  }, [lesson?.id, isSqlite]);

  const handleSubmit = useCallback(async () => {
    if (!courseId || !lessonId || !query.trim()) return;

    // For SQLite: show local results immediately
    if (isSqlite && sqlite.isReady) {
      const result = sqlite.execute(query.trim());
      setLocalResult(result);
    }

    // Always submit to server for grading
    try {
      setError('');
      setCurrentSubmission(null);
      if (!isSqlite) setLocalResult(null);
      const submission = await submitMutation.mutateAsync(query.trim());
      setCurrentSubmission(submission);
    } catch (err) {
      setError(getApiErrorMessage(err, t('page.failedSubmit')));
    }
  }, [courseId, lessonId, query, isSqlite, sqlite, submitMutation]);

  // Ctrl+Enter is handled by Monaco editor's onExecute prop

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
        <h2 className="text-xl font-semibold mb-2">{t('page.notFound')}</h2>
        <Link to={`/courses/${courseId}`} className="text-primary hover:underline">
          {t('page.backToCourse')}
        </Link>
      </div>
    );
  }

  const hints = lesson.hints || [];
  const maxAttempts = lesson.max_attempts;
  const attemptsUsed = submissions.length;
  const attemptsLeft = maxAttempts ? maxAttempts - attemptsUsed : undefined;
  const canSubmit = !maxAttempts || (attemptsLeft !== undefined && attemptsLeft > 0);
  const hasPractice = lesson.lesson_type !== 'theory';
  const hasTheory = lesson.lesson_type !== 'practice';

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex items-center gap-4">
        <Button
          variant="ghost"
          size="icon"
          onClick={() => navigate(`/courses/${courseId}`)}
        >
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

      {/* Tabs for mixed lessons */}
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

      {/* Theory content */}
      {hasTheory && (activeTab === 'theory' || lesson.lesson_type === 'theory') && (
        <Card>
          <CardContent className="prose prose-sm dark:prose-invert max-w-none pt-6">
            {lesson.theory_content ? (
              <ReactMarkdown
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

      {/* Attachments */}
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

      {/* Practice content */}
      {hasPractice && (activeTab === 'practice' || lesson.lesson_type === 'practice') && (
        <div className="grid gap-6 lg:grid-cols-2">
          {/* Left: Task description */}
          <div className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>{t('page.task')}</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="whitespace-pre-wrap">
                  {lesson.practice_description || t('page.defaultTaskDescription')}
                </p>
              </CardContent>
            </Card>

            {/* Hints */}
            {hints.length > 0 && (
              <Card>
                <CardHeader className="pb-2">
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-base flex items-center gap-2">
                      <Lightbulb className="h-4 w-4" />
                      {t('page.hints')}
                    </CardTitle>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setShowHint(!showHint)}
                    >
                      {showHint ? t('page.hide') : t('page.show')}
                    </Button>
                  </div>
                </CardHeader>
                {showHint && (
                  <CardContent>
                    <div className="flex items-center justify-between mb-2">
                      <Button
                        variant="ghost"
                        size="icon"
                        disabled={hintIndex === 0}
                        onClick={() => setHintIndex((i) => i - 1)}
                      >
                        <ChevronLeft className="h-4 w-4" />
                      </Button>
                      <span className="text-sm text-muted-foreground">
                        {t('page.hintOf', { current: hintIndex + 1, total: hints.length })}
                      </span>
                      <Button
                        variant="ghost"
                        size="icon"
                        disabled={hintIndex >= hints.length - 1}
                        onClick={() => setHintIndex((i) => i + 1)}
                      >
                        <ChevronRight className="h-4 w-4" />
                      </Button>
                    </div>
                    <p className="text-sm bg-muted p-3 rounded-md">{hints[hintIndex]}</p>
                  </CardContent>
                )}
              </Card>
            )}

            {/* Dataset schema */}
            {lesson.dataset && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">{t('page.databaseSchema')}</CardTitle>
                  <CardDescription>{lesson.dataset.name}</CardDescription>
                </CardHeader>
                <CardContent>
                  <pre className="text-xs bg-muted p-3 rounded-md overflow-auto max-h-48">
                    {lesson.dataset.schema_sql}
                  </pre>
                </CardContent>
              </Card>
            )}
          </div>

          {/* Right: Query editor and results */}
          <div className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>{t('page.yourQuery')}</CardTitle>
                <CardDescription>
                  {t('page.pressCtrlEnter')}
                  {maxAttempts && ` \u2022 ${t('page.attemptsLeft', { count: attemptsLeft })}`}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <SqlEditor
                  value={query}
                  onChange={setQuery}
                  height="192px"
                  readOnly={!canSubmit}
                  onExecute={handleSubmit}
                  placeholder={t('page.queryPlaceholder')}
                />
                <div className="flex items-center justify-between mt-4">
                  <span className="text-xs text-muted-foreground">
                    {t('page.timeLimit', { seconds: lesson.time_limit_seconds })}
                  </span>
                  <Button
                    onClick={handleSubmit}
                    disabled={submitMutation.isPending || !query.trim() || !canSubmit}
                  >
                    {submitMutation.isPending ? (
                      <Spinner size="sm" className="mr-2" />
                    ) : (
                      <Play className="h-4 w-4 mr-2" />
                    )}
                    {t('page.runQuery')}
                  </Button>
                </div>
              </CardContent>
            </Card>

            {/* Local SQLite preview (instant) */}
            {isSqlite && localResult && (
              <Card>
                <CardHeader className="pb-2">
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-base">{t('page.queryOutput')}</CardTitle>
                    <Badge variant="outline">
                      {localResult.execution_time_ms}ms ({t('page.local')})
                    </Badge>
                  </div>
                </CardHeader>
                <CardContent>
                  {localResult.error_message && (
                    <Alert variant="destructive" className="mb-4">
                      <AlertDescription className="font-mono text-xs">
                        {localResult.error_message}
                      </AlertDescription>
                    </Alert>
                  )}
                  {localResult.success && localResult.columns.length > 0 && (
                    <div className="overflow-auto max-h-48 border rounded-md">
                      <Table className="w-full text-sm">
                        <TableHeader className="bg-muted sticky top-0">
                          <TableRow>
                            {localResult.columns.map((col, i) => (
                              <TableHead key={i} className="px-2 py-1 text-left font-medium border-b">
                                {col}
                              </TableHead>
                            ))}
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {localResult.rows.slice(0, 10).map((row, i) => (
                            <TableRow key={i} className="border-b">
                              {(row as unknown[]).map((cell, j) => (
                                <TableCell key={j} className="px-2 py-1 font-mono text-xs">
                                  {cell === null ? (
                                    <span className="text-muted-foreground italic">NULL</span>
                                  ) : (
                                    String(cell)
                                  )}
                                </TableCell>
                              ))}
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </div>
                  )}
                  {localResult.success && localResult.affected_rows > 0 && (
                    <p className="text-sm text-muted-foreground">
                      {t('page.rowsAffected', { count: localResult.affected_rows })}
                    </p>
                  )}
                </CardContent>
              </Card>
            )}

            {/* Grading result */}
            {currentSubmission && (
              <Card>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-base">{t('page.result')}</CardTitle>
                    {currentSubmission.is_correct ? (
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
                  {currentSubmission.status === 'error' && (
                    <Alert variant="destructive" className="mb-4">
                      <AlertDescription>{currentSubmission.error_message}</AlertDescription>
                    </Alert>
                  )}

                  {currentSubmission.result && (
                    <div className="overflow-auto">
                      <Table className="w-full text-sm">
                        <TableHeader>
                          <TableRow className="border-b">
                            {currentSubmission.result.columns.map((col: string, i: number) => (
                              <TableHead key={i} className="px-2 py-1 text-left font-medium">
                                {col}
                              </TableHead>
                            ))}
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {currentSubmission.result.rows.slice(0, 10).map((row: unknown[], i: number) => (
                            <TableRow key={i} className="border-b">
                              {row.map((cell, j) => (
                                <TableCell key={j} className="px-2 py-1">
                                  {String(cell ?? 'NULL')}
                                </TableCell>
                              ))}
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                      {currentSubmission.result.row_count > 10 && (
                        <p className="text-xs text-muted-foreground mt-2">
                          {t('page.showingRows', { shown: 10, total: currentSubmission.result.row_count })}
                        </p>
                      )}
                    </div>
                  )}

                  <div className="flex items-center justify-between mt-4 text-sm text-muted-foreground">
                    <span>
                      {t('page.score', { score: currentSubmission.score, max: lesson.max_score })}
                    </span>
                    <span>{t('page.time', { ms: currentSubmission.execution_time_ms })}</span>
                  </div>
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
