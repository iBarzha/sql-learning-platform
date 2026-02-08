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
  database_type: 'postgresql' | 'sqlite' | 'mysql' | 'mariadb' | 'mongodb' | 'redis';
  is_published: boolean;
  enrollment_key?: string;
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
  partial_match: boolean;
  max_score: number;
  time_limit_seconds: number;
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
  assignment: string;
  assignment_title?: string;
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

export interface SubmissionFeedback {
  result_match?: boolean;
  keywords_found?: string[];
  keywords_missing?: string[];
  forbidden_used?: string[];
  hints?: string[];
  message?: string;
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
