import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Spinner } from '@/components/ui/spinner';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Progress } from '@/components/ui/progress';
import {
  Server,
  Database,
  Cpu,
  HardDrive,
  Box,
  Users,
  BookOpen,
  ListChecks,
  FileCode,
  Activity,
  RefreshCcw,
} from 'lucide-react';
import { fetchAdminDashboard } from '@/api/adminDashboard';
import { getApiErrorMessage } from '@/lib/utils';

function formatUptime(seconds: number): string {
  if (!seconds) return '—';
  const d = Math.floor(seconds / 86400);
  const h = Math.floor((seconds % 86400) / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (d > 0) return `${d}d ${h}h`;
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
}

function formatRelative(iso: string | null): string {
  if (!iso) return 'never';
  const diffMs = Date.now() - new Date(iso).getTime();
  const sec = Math.floor(diffMs / 1000);
  if (sec < 60) return `${sec}s ago`;
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min}m ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}h ago`;
  return `${Math.floor(hr / 24)}d ago`;
}

interface MetricBarProps {
  label: string;
  used: string;
  total: string;
  percent: number;
  icon: React.ComponentType<{ className?: string }>;
}

function MetricBar({ label, used, total, percent, icon: Icon }: MetricBarProps) {
  const tone = percent > 90 ? 'destructive' : percent > 75 ? 'warning' : 'success';
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-sm">
        <span className="flex items-center gap-2 text-muted-foreground">
          <Icon className="h-4 w-4" />
          {label}
        </span>
        <span className="font-mono">
          {used} / {total} <span className="text-muted-foreground">({percent.toFixed(1)}%)</span>
        </span>
      </div>
      <Progress value={percent} className={tone === 'destructive' ? 'bg-destructive/20' : tone === 'warning' ? 'bg-yellow-500/20' : ''} />
    </div>
  );
}

interface StatTileProps {
  label: string;
  value: number | string;
  hint?: string;
  icon: React.ComponentType<{ className?: string }>;
}

function StatTile({ label, value, hint, icon: Icon }: StatTileProps) {
  return (
    <div className="rounded-xl border border-border/60 bg-card/50 p-4">
      <div className="flex items-center gap-2 text-sm text-muted-foreground mb-1">
        <Icon className="h-4 w-4" />
        {label}
      </div>
      <div className="text-2xl font-semibold">{value}</div>
      {hint && <div className="text-xs text-muted-foreground mt-1">{hint}</div>}
    </div>
  );
}

export function SettingsPage() {
  const { data, isLoading, error, refetch, isFetching, dataUpdatedAt } = useQuery({
    queryKey: ['admin', 'dashboard'],
    queryFn: fetchAdminDashboard,
    refetchInterval: 15000,
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Spinner size="lg" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <Alert variant="destructive">
        <AlertDescription>{getApiErrorMessage(error, 'Failed to load admin dashboard')}</AlertDescription>
      </Alert>
    );
  }

  const { server, database, sandbox, stats, activity } = data;
  const lastUpdate = dataUpdatedAt ? formatRelative(new Date(dataUpdatedAt).toISOString()) : '—';

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold">Admin Dashboard</h1>
          <p className="text-muted-foreground">Live system, database and application metrics</p>
        </div>
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <RefreshCcw className={`h-4 w-4 ${isFetching ? 'animate-spin' : ''}`} />
          <span>Updated {lastUpdate}</span>
          <button onClick={() => refetch()} className="ml-2 underline hover:text-foreground">refresh</button>
        </div>
      </div>

      {/* Top stats */}
      <div className="grid gap-3 sm:grid-cols-2 md:grid-cols-4 lg:grid-cols-6">
        <StatTile label="Users" value={stats.users.total} hint={`${stats.users.active_24h} active 24h`} icon={Users} />
        <StatTile label="Courses" value={stats.courses.total} hint={`${stats.courses.published} published`} icon={BookOpen} />
        <StatTile label="Lessons" value={stats.lessons.total} hint={`${stats.lessons.published} published`} icon={BookOpen} />
        <StatTile label="Exercises" value={stats.exercises.total} icon={ListChecks} />
        <StatTile label="Datasets" value={stats.datasets.total} hint={`${stats.datasets.system} system / ${stats.datasets.instructor_owned} owned`} icon={FileCode} />
        <StatTile label="Submissions" value={stats.submissions.total} hint={`${stats.submissions.last_24h} last 24h`} icon={Activity} />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        {/* Server card */}
        <Card variant="glass">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Server className="h-5 w-5" />
              Server
            </CardTitle>
            <CardDescription>
              {server ? `Uptime: ${formatUptime(server.uptime_seconds)} · ${server.cpu_count} CPU` : 'metrics unavailable'}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {server ? (
              <>
                <MetricBar
                  label="CPU"
                  used={`${server.cpu_percent.toFixed(1)}%`}
                  total="100%"
                  percent={server.cpu_percent}
                  icon={Cpu}
                />
                <MetricBar
                  label="Memory"
                  used={`${(server.memory_used_mb / 1024).toFixed(2)} GB`}
                  total={`${(server.memory_total_mb / 1024).toFixed(2)} GB`}
                  percent={server.memory_percent}
                  icon={Server}
                />
                <MetricBar
                  label="Disk"
                  used={`${server.disk_used_gb} GB`}
                  total={`${server.disk_total_gb} GB`}
                  percent={server.disk_percent}
                  icon={HardDrive}
                />
              </>
            ) : (
              <p className="text-sm text-muted-foreground">psutil not available on this server</p>
            )}
          </CardContent>
        </Card>

        {/* Database card */}
        <Card variant="glass">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Database className="h-5 w-5" />
              Database
              {database.connected ? (
                <Badge variant="success">connected</Badge>
              ) : (
                <Badge variant="destructive">offline</Badge>
              )}
            </CardTitle>
            <CardDescription>
              {database.engine} @ {database.host}:{database.port} · {database.name} · size: {database.size_pretty ?? '—'}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="text-sm text-muted-foreground mb-2">Top tables by row count</div>
            <div className="space-y-1">
              {database.tables.length === 0 && <p className="text-sm text-muted-foreground">No tables yet</p>}
              {database.tables.map((t) => (
                <div key={t.name} className="flex items-center justify-between text-sm py-1 border-b border-border/40 last:border-0">
                  <span className="font-mono">{t.name}</span>
                  <span className="text-muted-foreground">
                    {t.rows.toLocaleString()} rows · {t.size}
                  </span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Sandbox card */}
        <Card variant="glass">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Box className="h-5 w-5" />
              Sandbox Pool
            </CardTitle>
            <CardDescription>Container availability per database type</CardDescription>
          </CardHeader>
          <CardContent>
            {sandbox.error ? (
              <p className="text-sm text-destructive">{sandbox.error}</p>
            ) : (
              <div className="space-y-2 text-sm">
                {Object.entries(sandbox).map(([k, v]) => {
                  if (typeof v === 'object' && v !== null) {
                    return (
                      <div key={k}>
                        <div className="text-muted-foreground capitalize mb-1">{k.replace(/_/g, ' ')}</div>
                        <div className="grid grid-cols-3 gap-2">
                          {Object.entries(v as Record<string, unknown>).map(([dbType, val]) => (
                            <div key={dbType} className="rounded-md border border-border/60 px-2 py-1">
                              <span className="font-mono text-xs">{dbType}</span>{' '}
                              <span className="text-muted-foreground">
                                {typeof val === 'boolean' ? (val ? 'ok' : 'fail') : String(val)}
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    );
                  }
                  return (
                    <div key={k} className="flex items-center justify-between">
                      <span className="text-muted-foreground capitalize">{k.replace(/_/g, ' ')}</span>
                      <span className="font-mono">{String(v)}</span>
                    </div>
                  );
                })}
              </div>
            )}
          </CardContent>
        </Card>

        {/* User breakdown */}
        <Card variant="glass">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Users className="h-5 w-5" />
              Users by role
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <div className="flex items-center justify-between border-b border-border/40 pb-2">
              <span>Admins</span>
              <Badge variant="outline">{stats.users.admins}</Badge>
            </div>
            <div className="flex items-center justify-between border-b border-border/40 pb-2">
              <span>Instructors</span>
              <Badge variant="outline">{stats.users.instructors}</Badge>
            </div>
            <div className="flex items-center justify-between border-b border-border/40 pb-2">
              <span>Students</span>
              <Badge variant="outline">{stats.users.students}</Badge>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">Active in last 24h</span>
              <Badge>{stats.users.active_24h}</Badge>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Recent activity */}
      <div className="grid gap-4 lg:grid-cols-2">
        <Card variant="glass">
          <CardHeader>
            <CardTitle>Recent users</CardTitle>
          </CardHeader>
          <CardContent>
            {activity.recent_users.length === 0 ? (
              <p className="text-sm text-muted-foreground">No users</p>
            ) : (
              <div className="space-y-1">
                {activity.recent_users.map((u) => (
                  <div key={u.id} className="flex items-center justify-between text-sm py-1 border-b border-border/40 last:border-0">
                    <div>
                      <div className="font-medium">{u.full_name || u.email}</div>
                      <div className="text-xs text-muted-foreground">{u.email}</div>
                    </div>
                    <div className="text-right">
                      <Badge variant="outline" className="text-xs">{u.role}</Badge>
                      <div className="text-xs text-muted-foreground mt-0.5">
                        {u.last_login ? `seen ${formatRelative(u.last_login)}` : 'never logged in'}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        <Card variant="glass">
          <CardHeader>
            <CardTitle>Recent submissions</CardTitle>
          </CardHeader>
          <CardContent>
            {activity.recent_submissions.length === 0 ? (
              <p className="text-sm text-muted-foreground">No submissions</p>
            ) : (
              <div className="space-y-1">
                {activity.recent_submissions.map((s) => (
                  <div key={s.id} className="flex items-center justify-between text-sm py-1 border-b border-border/40 last:border-0">
                    <div className="min-w-0 flex-1">
                      <div className="font-medium truncate">{s.target || '—'}</div>
                      <div className="text-xs text-muted-foreground truncate">
                        {s.student_email}{s.exercise ? ` · ${s.exercise}` : ''}
                      </div>
                    </div>
                    <div className="text-right ml-3 shrink-0">
                      {s.is_correct ? (
                        <Badge variant="success" className="text-xs">correct</Badge>
                      ) : (
                        <Badge variant="destructive" className="text-xs">wrong</Badge>
                      )}
                      <div className="text-xs text-muted-foreground mt-0.5">{formatRelative(s.submitted_at)}</div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
