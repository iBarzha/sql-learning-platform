export interface User {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  full_name: string;
  role: 'student' | 'instructor' | 'admin';
  must_change_password: boolean;
  is_active: boolean;
  created_at: string;
  last_login?: string | null;
  avatar_url?: string | null;
}

export interface AuthTokens {
  access: string;
  refresh: string;
}

export interface AuthResponse {
  user: User;
  tokens: AuthTokens;
}

export interface Course {
  id: string;
  title: string;
  description: string;
  instructor: User;
  instructor_name?: string;
  database_type: 'postgresql' | 'sqlite' | 'mariadb' | 'mongodb' | 'redis';
  is_published: boolean;
  course_code?: string;
  max_students?: number;
  start_date?: string;
  end_date?: string;
  student_count: number;
  assignment_count: number;
  lesson_count: number;
  is_enrolled?: boolean;
  datasets?: Dataset[];
  created_at: string;
  updated_at?: string;
}

export interface Dataset {
  id: string;
  name: string;
  description: string;
  schema_sql: string;
  seed_sql: string;
  is_default: boolean;
  created_at: string;
  updated_at: string;
}

export interface Assignment {
  id: string;
  title: string;
  description: string;
  instructions?: string;
  course: string;
  course_title?: string;
  database_type?: string;
  dataset?: Dataset;
  dataset_name?: string;
  query_type: 'select' | 'insert' | 'update' | 'delete' | 'ddl' | 'nosql';
  difficulty: 'easy' | 'medium' | 'hard';
  expected_query?: string;
  expected_result?: unknown;
  required_keywords: string[];
  forbidden_keywords: string[];
  order_matters: boolean;
  ignore_column_order?: boolean;
  partial_match: boolean;
  max_score: number;
  criteria_summary?: CriteriaSummary;
  time_limit_seconds: number | null;
  max_attempts?: number;
  hints: string[];
  due_date?: string;
  is_published: boolean;
  order: number;
  submission_count?: number;
  average_score?: number;
  user_best_score?: number;
  user_completed?: boolean;
  user_attempts?: number;
  created_at: string;
  updated_at?: string;
}

export interface Submission {
  id: string;
  student: string;
  student_name?: string;
  assignment?: string;
  assignment_title?: string;
  lesson?: string;
  exercise?: string;
  query: string;
  status: 'pending' | 'running' | 'completed' | 'error' | 'timeout';
  result?: QueryResult;
  error_message?: string;
  execution_time_ms?: number;
  score?: number;
  is_correct: boolean;
  feedback?: SubmissionFeedback;
  attempt_number: number;
  submitted_at: string;
  graded_at?: string;
}

export interface QueryResult {
  columns: string[];
  rows: unknown[][];
  row_count: number;
}

export interface SubmissionCheck {
  code: string;
  name: string;
  passed: boolean;
  detail?: string;
}

export interface CriterionVerdict {
  id: string;
  name: string;
  passed: boolean;
  detail: string;
}

export interface ExerciseCriteria {
  enabled: string[];
  threshold: number;
}

export interface CriteriaSummary {
  criteria: { id: string; name: string }[];
  total: number;
  threshold: number;
}

export type CriterionKind = 'select' | 'dml' | 'nosql';

export interface CriterionInfo {
  id: string;
  name: string;
  description: string;
  kinds: CriterionKind[];
}

export interface SubmissionFeedback {
  mode?: 'result' | 'execution';
  result_match?: boolean;
  checks?: SubmissionCheck[];
  keywords_found?: string[];
  keywords_missing?: string[];
  forbidden_used?: string[];
  hints?: string[];
  message?: string;
  failed_datasets?: { name: string; targets?: string }[];
  datasets_checked?: number;
  missing_rows?: string[];
  extra_rows?: string[];
  criteria?: CriterionVerdict[];
  passed_count?: number;
  total?: number;
  threshold?: number;
}

export interface UserResult {
  id: string;
  student: User;
  assignment: string;
  assignment_title?: string;
  best_submission?: Submission;
  best_score: number;
  total_attempts: number;
  is_completed: boolean;
  first_completed_at?: string;
  last_attempt_at?: string;
}

/** One graded task of a student (lesson exercise or assignment), from `/results/`. */
export interface StudentResult {
  id: string;
  student: string;
  assignment: string | null;
  assignment_title: string | null;
  lesson: string | null;
  lesson_title: string | null;
  exercise: string | null;
  exercise_title: string | null;
  max_score: number;
  best_submission: string | null;
  best_score: number;
  total_attempts: number;
  is_completed: boolean;
  first_completed_at: string | null;
  last_attempt_at: string | null;
  extra_seconds: number;
  manual_score: number | null;
  manual_comment: string;
  manual_set_at: string | null;
  effective_score: number;
}

export interface ManualScoreData {
  manual_score: number | null;
  manual_comment: string;
}

/** Timer state of one timed lesson for one student. */
export interface StudentTimer {
  lesson_id: string;
  lesson_title: string;
  time_limit_seconds: number;
  started_at: string | null;
  deadline: string | null;
  remaining_seconds: number | null;
  extra_seconds: number;
}

export interface RegradeSummary {
  submissions: number;
  changed: number;
  truncated: boolean;
}

export interface Enrollment {
  id: string;
  student: User;
  course: string;
  course_title?: string;
  status: 'pending' | 'active' | 'completed' | 'dropped';
  grade?: number;
  enrolled_at: string;
  completed_at?: string;
}

export interface CourseProgress {
  course_id: string;
  course_title: string;
  total_assignments: number;
  completed_assignments: number;
  total_score: number;
  max_possible_score: number;
  completion_rate: number;
  percentage_score: number;
}

export interface ApiError {
  detail?: string;
  message?: string;
  [key: string]: unknown;
}

export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}
