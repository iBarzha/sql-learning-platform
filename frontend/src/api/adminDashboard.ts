import apiClient from './client';

export interface ServerMetrics {
  cpu_percent: number;
  cpu_count: number;
  memory_total_mb: number;
  memory_used_mb: number;
  memory_percent: number;
  disk_total_gb: number;
  disk_used_gb: number;
  disk_percent: number;
  uptime_seconds: number;
}

export interface DbTable {
  name: string;
  rows: number;
  size: string;
}

export interface DatabaseMetrics {
  engine: string;
  name: string;
  host: string;
  port: string;
  connected: boolean;
  size_pretty: string | null;
  tables: DbTable[];
  error?: string;
}

export interface SandboxMetrics {
  available?: Record<string, number>;
  total_executions?: number;
  in_use?: Record<string, number>;
  health?: Record<string, boolean>;
  error?: string;
  [key: string]: unknown;
}

export interface AppStats {
  users: { total: number; admins: number; instructors: number; students: number; active_24h: number };
  courses: { total: number; published: number; draft: number };
  modules: { total: number };
  lessons: { total: number; published: number };
  exercises: { total: number };
  datasets: { total: number; system: number; instructor_owned: number };
  submissions: { total: number; last_24h: number; last_7d: number; correct: number };
}

export interface RecentUser {
  id: string;
  email: string;
  full_name: string;
  role: string;
  created_at: string;
  last_login: string | null;
}

export interface RecentSubmission {
  id: string;
  student_email: string | null;
  target: string | null;
  exercise: string | null;
  is_correct: boolean;
  score: number | null;
  status: string;
  submitted_at: string;
}

export interface RecentActivity {
  recent_users: RecentUser[];
  recent_submissions: RecentSubmission[];
}

export interface AdminDashboard {
  server: ServerMetrics | null;
  database: DatabaseMetrics;
  sandbox: SandboxMetrics;
  stats: AppStats;
  activity: RecentActivity;
  generated_at: string;
}

export async function fetchAdminDashboard(): Promise<AdminDashboard> {
  const response = await apiClient.get<AdminDashboard>('/admin/dashboard/');
  return response.data;
}
