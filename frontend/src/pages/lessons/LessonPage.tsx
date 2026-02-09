import { useEffect, useState, useCallback } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Spinner } from '@/components/ui/spinner';
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
      const submission = await submitMutation.mutateAsync(query.trim());
      setCurrentSubmission(submission);
    } catch (err) {
      setError(getApiErrorMessage(err, 'Failed to submit query'));
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
        <h2 className="text-xl font-semibold mb-2">Lesson not found</h2>
        <Link to={`/courses/${courseId}`} className="text-primary hover:underline">
          Back to course
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
    <div className="space-y-6">
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
              Theory
            </>
          ) : lesson.lesson_type === 'practice' ? (
            <>
              <Code className="h-3 w-3 mr-1" />
              Practice
            </>
          ) : (
            'Mixed'
          )}
        </Badge>
        {hasPractice && lesson.user_completed && (
          <Badge variant="default" className="bg-green-500">
            <CheckCircle className="h-3 w-3 mr-1" />
            Completed
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
        <div className="flex gap-2 border-b">
          <button
            onClick={() => setActiveTab('theory')}
            className={`px-4 py-2 font-medium border-b-2 transition-colors ${
              activeTab === 'theory'
                ? 'border-primary text-primary'
                : 'border-transparent text-muted-foreground hover:text-foreground'
            }`}
          >
            <BookOpen className="h-4 w-4 inline mr-2" />
            Theory
          </button>
          <button
            onClick={() => setActiveTab('practice')}
            className={`px-4 py-2 font-medium border-b-2 transition-colors ${
              activeTab === 'practice'
                ? 'border-primary text-primary'
                : 'border-transparent text-muted-foreground hover:text-foreground'
            }`}
          >
            <Code className="h-4 w-4 inline mr-2" />
            Practice
          </button>
        </div>
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
              <p className="text-muted-foreground">No theory content available.</p>
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
              Attachments ({attachments.length})
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
                <CardTitle>Task</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="whitespace-pre-wrap">
                  {lesson.practice_description || 'Complete the SQL query.'}
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
                      Hints
                    </CardTitle>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setShowHint(!showHint)}
                    >
                      {showHint ? 'Hide' : 'Show'}
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
                        Hint {hintIndex + 1} of {hints.length}
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
                  <CardTitle className="text-base">Database Schema</CardTitle>
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
                <CardTitle>Your Query</CardTitle>
                <CardDescription>
                  Press Ctrl+Enter to submit
                  {maxAttempts && ` • ${attemptsLeft} attempts left`}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <SqlEditor
                  value={query}
                  onChange={setQuery}
                  height="192px"
                  readOnly={!canSubmit}
                  onExecute={handleSubmit}
                  placeholder="-- Write your SQL query here"
                />
                <div className="flex items-center justify-between mt-4">
                  <span className="text-xs text-muted-foreground">
                    Time limit: {lesson.time_limit_seconds}s
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
                    Run Query
                  </Button>
                </div>
              </CardContent>
            </Card>

            {/* Local SQLite preview (instant) */}
            {isSqlite && localResult && (
              <Card>
                <CardHeader className="pb-2">
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-base">Query Output</CardTitle>
                    <Badge variant="outline">
                      {localResult.execution_time_ms}ms (local)
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
                      <table className="w-full text-sm">
                        <thead className="bg-muted sticky top-0">
                          <tr>
                            {localResult.columns.map((col, i) => (
                              <th key={i} className="px-2 py-1 text-left font-medium border-b">
                                {col}
                              </th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {localResult.rows.slice(0, 10).map((row, i) => (
                            <tr key={i} className="border-b">
                              {(row as unknown[]).map((cell, j) => (
                                <td key={j} className="px-2 py-1 font-mono text-xs">
                                  {cell === null ? (
                                    <span className="text-muted-foreground italic">NULL</span>
                                  ) : (
                                    String(cell)
                                  )}
                                </td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                  {localResult.success && localResult.affected_rows > 0 && (
                    <p className="text-sm text-muted-foreground">
                      {localResult.affected_rows} row(s) affected
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
                    <CardTitle className="text-base">Result</CardTitle>
                    {currentSubmission.is_correct ? (
                      <Badge variant="default" className="bg-green-500">
                        <CheckCircle className="h-3 w-3 mr-1" />
                        Correct
                      </Badge>
                    ) : (
                      <Badge variant="destructive">
                        <XCircle className="h-3 w-3 mr-1" />
                        Incorrect
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
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="border-b">
                            {currentSubmission.result.columns.map((col: string, i: number) => (
                              <th key={i} className="px-2 py-1 text-left font-medium">
                                {col}
                              </th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {currentSubmission.result.rows.slice(0, 10).map((row: unknown[], i: number) => (
                            <tr key={i} className="border-b">
                              {row.map((cell, j) => (
                                <td key={j} className="px-2 py-1">
                                  {String(cell ?? 'NULL')}
                                </td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                      {currentSubmission.result.row_count > 10 && (
                        <p className="text-xs text-muted-foreground mt-2">
                          Showing 10 of {currentSubmission.result.row_count} rows
                        </p>
                      )}
                    </div>
                  )}

                  <div className="flex items-center justify-between mt-4 text-sm text-muted-foreground">
                    <span>
                      Score: {currentSubmission.score}/{lesson.max_score}
                    </span>
                    <span>Time: {currentSubmission.execution_time_ms}ms</span>
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
