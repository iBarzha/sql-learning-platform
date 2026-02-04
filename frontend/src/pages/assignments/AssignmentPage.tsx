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
import assignmentsApi from '@/api/assignments';
import submissionsApi from '@/api/submissions';
import type { Assignment, Submission } from '@/types';

export function AssignmentPage() {
  const { courseId, assignmentId } = useParams<{
    courseId: string;
    assignmentId: string;
  }>();
  const navigate = useNavigate();

  const [assignment, setAssignment] = useState<Assignment | null>(null);
  const [submissions, setSubmissions] = useState<Submission[]>([]);
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [currentSubmission, setCurrentSubmission] = useState<Submission | null>(null);
  const [showHint, setShowHint] = useState(false);
  const [hintIndex, setHintIndex] = useState(0);
  const [error, setError] = useState('');

  useEffect(() => {
    if (courseId && assignmentId) {
      loadAssignment();
    }
  }, [courseId, assignmentId]);

  async function loadAssignment() {
    try {
      setLoading(true);
      const [assignmentData, submissionsData] = await Promise.all([
        assignmentsApi.get(courseId!, assignmentId!),
        submissionsApi.getMySubmissions(courseId!, assignmentId!).catch(() => []),
      ]);
      setAssignment(assignmentData);
      setSubmissions(submissionsData);

      // Set initial query from last submission if exists
      if (submissionsData.length > 0) {
        setQuery(submissionsData[0].query);
      }
    } catch (err) {
      console.error('Failed to load assignment:', err);
      setError('Failed to load assignment');
    } finally {
      setLoading(false);
    }
  }

  const handleSubmit = useCallback(async () => {
    if (!courseId || !assignmentId || !query.trim()) return;

    try {
      setSubmitting(true);
      setError('');
      setCurrentSubmission(null);

      const submission = await submissionsApi.submit(courseId, assignmentId, {
        query: query.trim(),
      });

      setCurrentSubmission(submission);
      setSubmissions((prev) => [submission, ...prev]);
    } catch (err) {
      const message = (err as { response?: { data?: { detail?: string } } })
        ?.response?.data?.detail || 'Failed to submit query';
      setError(message);
    } finally {
      setSubmitting(false);
    }
  }, [courseId, assignmentId, query]);

  // Keyboard shortcut for submit
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        e.preventDefault();
        handleSubmit();
      }
    }
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleSubmit]);

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
              <textarea
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder={`-- Write your ${assignment.query_type.toUpperCase()} query here`}
                className="w-full h-48 p-3 font-mono text-sm bg-muted rounded-md border-0 resize-none focus:outline-none focus:ring-2 focus:ring-primary"
                disabled={!canSubmit}
              />
              <div className="flex items-center justify-between mt-4">
                <span className="text-xs text-muted-foreground">
                  Time limit: {assignment.time_limit_seconds}s
                </span>
                <Button
                  onClick={handleSubmit}
                  disabled={submitting || !query.trim() || !canSubmit}
                >
                  {submitting ? (
                    <Spinner size="sm" className="mr-2" />
                  ) : (
                    <Play className="h-4 w-4 mr-2" />
                  )}
                  Run Query
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* Current submission result */}
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
