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
  Clock,
  Play,
  Lightbulb,
  ChevronRight,
  ChevronLeft,
} from 'lucide-react';
import type { Assignment, Submission } from '@/types';
import { useAssignment } from '@/hooks/queries/useAssignments';
import { useMySubmissions, useSubmitAssignment } from '@/hooks/queries/useSubmissions';
import { getApiErrorMessage } from '@/lib/utils';
import { SqlEditor } from '@/components/editor/SqlEditor';
import { useSqlite } from '@/hooks/useSqlite';
import type { LocalQueryResult } from '@/lib/sqljs';

export function AssignmentPage() {
  const { courseId, assignmentId } = useParams<{
    courseId: string;
    assignmentId: string;
  }>();
  const navigate = useNavigate();

  const { data: assignment, isLoading: assignmentLoading } = useAssignment(courseId, assignmentId);
  const { data: submissions = [], isLoading: subsLoading } = useMySubmissions(courseId, assignmentId);
  const submitMutation = useSubmitAssignment(courseId!, assignmentId!);
  const loading = assignmentLoading || subsLoading;

  const [query, setQuery] = useState('');
  const [queryInitialized, setQueryInitialized] = useState(false);
  const [currentSubmission, setCurrentSubmission] = useState<Submission | null>(null);
  const [localResult, setLocalResult] = useState<LocalQueryResult | null>(null);
  const [showHint, setShowHint] = useState(false);
  const [hintIndex, setHintIndex] = useState(0);
  const [error, setError] = useState('');

  // Client-side SQLite for instant preview
  const sqlite = useSqlite();

  // Set initial query from last submission
  useEffect(() => {
    if (!queryInitialized && !loading && assignment) {
      if (submissions.length > 0) {
        setQuery(submissions[0].query);
      }
      setQueryInitialized(true);
    }
  }, [loading, assignment, submissions, queryInitialized]);

  // Initialize local SQLite DB for SQLite courses
  const isSqlite = assignment?.database_type === 'sqlite';
  useEffect(() => {
    if (assignment && isSqlite && assignment.dataset) {
      sqlite.initDatabase(assignment.dataset.schema_sql, assignment.dataset.seed_sql);
    }
  }, [assignment?.id, isSqlite]);

  const handleSubmit = useCallback(async () => {
    if (!courseId || !assignmentId || !query.trim()) return;

    // For SQLite: show local results immediately
    if (isSqlite && sqlite.isReady) {
      const result = sqlite.execute(query.trim());
      setLocalResult(result);
    }

    // Always submit to server for grading
    try {
      setError('');
      setCurrentSubmission(null);
      const submission = await submitMutation.mutateAsync({
        query: query.trim(),
      });
      setCurrentSubmission(submission);
    } catch (err) {
      setError(getApiErrorMessage(err, 'Failed to submit query'));
    }
  }, [courseId, assignmentId, query, isSqlite, sqlite, submitMutation]);

  // Ctrl+Enter is handled by Monaco editor's onExecute prop

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Spinner size="lg" />
      </div>
    );
  }

  if (!assignment) {
    return (
      <div className="text-center py-12">
        <h2 className="text-xl font-semibold mb-2">Assignment not found</h2>
        <Link to={`/courses/${courseId}`} className="text-primary hover:underline">
          Back to course
        </Link>
      </div>
    );
  }

  const hints = assignment.hints || [];
  const maxAttempts = assignment.max_attempts;
  const attemptsUsed = submissions.length;
  const attemptsLeft = maxAttempts ? maxAttempts - attemptsUsed : undefined;
  const canSubmit = !maxAttempts || attemptsLeft! > 0;

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
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold">{assignment.title}</h1>
            <Badge
              variant={
                assignment.difficulty === 'easy'
                  ? 'secondary'
                  : assignment.difficulty === 'medium'
                  ? 'outline'
                  : 'destructive'
              }
            >
              {assignment.difficulty}
            </Badge>
          </div>
          <p className="text-muted-foreground">
            {assignment.course_title} • {assignment.query_type.toUpperCase()}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {assignment.user_completed && (
            <Badge variant="default" className="bg-green-500">
              <CheckCircle className="h-3 w-3 mr-1" />
              Completed
            </Badge>
          )}
          {maxAttempts && (
            <Badge variant="outline">
              {attemptsLeft} attempts left
            </Badge>
          )}
        </div>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Left: Instructions */}
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Instructions</CardTitle>
            </CardHeader>
            <CardContent className="prose prose-sm dark:prose-invert max-w-none">
              <p className="whitespace-pre-wrap">{assignment.description}</p>
              {assignment.instructions && (
                <>
                  <h4>Details</h4>
                  <p className="whitespace-pre-wrap">{assignment.instructions}</p>
                </>
              )}
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
                  <p className="text-sm bg-muted p-3 rounded-md">
                    {hints[hintIndex]}
                  </p>
                </CardContent>
              )}
            </Card>
          )}

          {/* Dataset info */}
          {assignment.dataset && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Dataset</CardTitle>
                <CardDescription>{assignment.dataset_name}</CardDescription>
              </CardHeader>
              <CardContent>
                <pre className="text-xs bg-muted p-3 rounded-md overflow-auto max-h-48">
                  {assignment.dataset.schema_sql}
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
                Write your SQL query and press Ctrl+Enter to submit
              </CardDescription>
            </CardHeader>
            <CardContent>
              <SqlEditor
                value={query}
                onChange={setQuery}
                height="192px"
                readOnly={!canSubmit}
                onExecute={handleSubmit}
                placeholder={`-- Write your ${assignment.query_type.toUpperCase()} query here`}
              />
              <div className="flex items-center justify-between mt-4">
                <span className="text-xs text-muted-foreground">
                  Time limit: {assignment.time_limit_seconds}s
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
                    <AlertDescription>
                      {currentSubmission.error_message}
                    </AlertDescription>
                  </Alert>
                )}

                {currentSubmission.result && (
                  <div className="overflow-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b">
                          {currentSubmission.result.columns.map((col, i) => (
                            <th key={i} className="px-2 py-1 text-left font-medium">
                              {col}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {currentSubmission.result.rows.slice(0, 10).map((row, i) => (
                          <tr key={i} className="border-b">
                            {(row as unknown[]).map((cell, j) => (
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

                {currentSubmission.feedback && (
                  <div className="mt-4 space-y-2">
                    {currentSubmission.feedback.message && (
                      <p className="text-sm">{currentSubmission.feedback.message}</p>
                    )}
                    {currentSubmission.feedback.keywords_missing &&
                      currentSubmission.feedback.keywords_missing.length > 0 && (
                        <p className="text-sm text-yellow-600">
                          Missing keywords:{' '}
                          {currentSubmission.feedback.keywords_missing.join(', ')}
                        </p>
                      )}
                    {currentSubmission.feedback.forbidden_used &&
                      currentSubmission.feedback.forbidden_used.length > 0 && (
                        <p className="text-sm text-red-600">
                          Forbidden keywords used:{' '}
                          {currentSubmission.feedback.forbidden_used.join(', ')}
                        </p>
                      )}
                  </div>
                )}

                <div className="flex items-center justify-between mt-4 text-sm text-muted-foreground">
                  <span>
                    Score: {currentSubmission.score}/{assignment.max_score}
                  </span>
                  <span>
                    Execution time: {currentSubmission.execution_time_ms}ms
                  </span>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Submission history */}
          {submissions.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Submission History</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {submissions.slice(0, 5).map((sub) => (
                    <div
                      key={sub.id}
                      className="flex items-center justify-between p-2 rounded-md bg-muted/50"
                    >
                      <div className="flex items-center gap-2">
                        {sub.is_correct ? (
                          <CheckCircle className="h-4 w-4 text-green-500" />
                        ) : sub.status === 'error' ? (
                          <XCircle className="h-4 w-4 text-red-500" />
                        ) : (
                          <Clock className="h-4 w-4 text-yellow-500" />
                        )}
                        <span className="text-sm">
                          Attempt #{sub.attempt_number}
                        </span>
                      </div>
                      <div className="flex items-center gap-4 text-sm text-muted-foreground">
                        <span>Score: {sub.score}</span>
                        <span>
                          {new Date(sub.submitted_at).toLocaleTimeString()}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
