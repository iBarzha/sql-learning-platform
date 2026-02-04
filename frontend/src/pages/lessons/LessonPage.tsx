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
import lessonsApi, { type Lesson } from '@/api/lessons';
import ReactMarkdown from 'react-markdown';

export function LessonPage() {
  const { courseId, lessonId } = useParams<{ courseId: string; lessonId: string }>();
  const navigate = useNavigate();

  const [lesson, setLesson] = useState<Lesson | null>(null);
  const [submissions, setSubmissions] = useState<any[]>([]);
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [currentSubmission, setCurrentSubmission] = useState<any>(null);
  const [showHint, setShowHint] = useState(false);
  const [hintIndex, setHintIndex] = useState(0);
  const [error, setError] = useState('');
  const [activeTab, setActiveTab] = useState<'theory' | 'practice'>('theory');

  useEffect(() => {
    if (courseId && lessonId) {
      loadLesson();
    }
  }, [courseId, lessonId]);

  async function loadLesson() {
    try {
      setLoading(true);
      const lessonData = await lessonsApi.get(courseId!, lessonId!);
      setLesson(lessonData);

      // Load submissions if lesson has practice
      if (lessonData.lesson_type !== 'theory') {
        try {
          const subs = await lessonsApi.getMySubmissions(courseId!, lessonId!);
          setSubmissions(subs);
          if (subs.length > 0) {
            setQuery(subs[0].query);
          } else if (lessonData.practice_initial_code) {
            setQuery(lessonData.practice_initial_code);
          }
        } catch {
          // Ignore submission load errors
        }
      }

      // Set initial tab based on lesson type
      if (lessonData.lesson_type === 'practice') {
        setActiveTab('practice');
      }
    } catch (err) {
      console.error('Failed to load lesson:', err);
      setError('Failed to load lesson');
    } finally {
      setLoading(false);
    }
  }

  const handleSubmit = useCallback(async () => {
    if (!courseId || !lessonId || !query.trim()) return;

    try {
      setSubmitting(true);
      setError('');
      setCurrentSubmission(null);

      const submission = await lessonsApi.submit(courseId, lessonId, query.trim());
      setCurrentSubmission(submission);
      setSubmissions((prev) => [submission, ...prev]);
    } catch (err) {
      const message = (err as { response?: { data?: { detail?: string } } })
        ?.response?.data?.detail || 'Failed to submit query';
      setError(message);
    } finally {
      setSubmitting(false);
    }
  }, [courseId, lessonId, query]);

  // Keyboard shortcut
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
              <ReactMarkdown>{lesson.theory_content}</ReactMarkdown>
            ) : (
              <p className="text-muted-foreground">No theory content available.</p>
            )}
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
                <textarea
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="-- Write your SQL query here"
                  className="w-full h-48 p-3 font-mono text-sm bg-muted rounded-md border-0 resize-none focus:outline-none focus:ring-2 focus:ring-primary"
                  disabled={!canSubmit}
                />
                <div className="flex items-center justify-between mt-4">
                  <span className="text-xs text-muted-foreground">
                    Time limit: {lesson.time_limit_seconds}s
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

            {/* Result */}
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
                          {currentSubmission.result.rows.slice(0, 10).map((row: any[], i: number) => (
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
