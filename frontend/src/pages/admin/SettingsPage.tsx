import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
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

type Translate = (key: string, options?: Record<string, unknown>) => string;

function formatUptime(t: Translate, seconds: number): string {
  if (!seconds) return '—';
  const d = Math.floor(seconds / 86400);
  const h = Math.floor((seconds % 86400) / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (d > 0) return t('dashboard.uptime.dh', { d, h });
  if (h > 0) return t('dashboard.uptime.hm', { h, m });
  return t('dashboard.uptime.m', { m });
}

function formatRelative(t: Translate, iso: string | null): string {
  if (!iso) return t('dashboard.never');
  const diffMs = Date.now() - new Date(iso).getTime();
  const sec = Math.floor(diffMs / 1000);
  if (sec < 60) return t('dashboard.ago.s', { n: sec });
  const min = Math.floor(sec / 60);
  if (min < 60) return t('dashboard.ago.m', { n: min });
  const hr = Math.floor(min / 60);
  if (hr < 24) return t('dashboard.ago.h', { n: hr });
  return t('dashboard.ago.d', { n: Math.floor(hr / 24) });
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
  const { t } = useTranslation('admin');
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
        <AlertDescription>{getApiErrorMessage(error, t('dashboard.loadError'))}</AlertDescription>
      </Alert>
    );
  }

  const { server, database, sandbox, stats, activity } = data;
  const lastUpdate = dataUpdatedAt ? formatRelative(t, new Date(dataUpdatedAt).toISOString()) : '—';

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold">{t('dashboard.title')}</h1>
          <p className="text-muted-foreground">{t('dashboard.subtitle')}</p>
        </div>
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <RefreshCcw className={`h-4 w-4 ${isFetching ? 'animate-spin' : ''}`} />
          <span>{t('dashboard.updated', { when: lastUpdate })}</span>
          <button onClick={() => refetch()} className="ml-2 underline hover:text-foreground">{t('dashboard.refresh')}</button>
        </div>
      </div>

      {/* Top stats */}
      <div className="grid gap-3 sm:grid-cols-2 md:grid-cols-4 lg:grid-cols-6">
        <StatTile label={t('dashboard.tiles.users')} value={stats.users.total} hint={t('dashboard.tiles.usersHint', { count: stats.users.active_24h })} icon={Users} />
        <StatTile label={t('dashboard.tiles.courses')} value={stats.courses.total} hint={t('dashboard.tiles.coursesHint', { count: stats.courses.published })} icon={BookOpen} />
        <StatTile label={t('dashboard.tiles.lessons')} value={stats.lessons.total} hint={t('dashboard.tiles.lessonsHint', { count: stats.lessons.published })} icon={BookOpen} />
        <StatTile label={t('dashboard.tiles.exercises')} value={stats.exercises.total} icon={ListChecks} />
        <StatTile label={t('dashboard.tiles.datasets')} value={stats.datasets.total} hint={t('dashboard.tiles.datasetsHint', { system: stats.datasets.system, owned: stats.datasets.instructor_owned })} icon={FileCode} />
        <StatTile label={t('dashboard.tiles.submissions')} value={stats.submissions.total} hint={t('dashboard.tiles.submissionsHint', { count: stats.submissions.last_24h })} icon={Activity} />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        {/* Server card */}
        <Card variant="glass">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Server className="h-5 w-5" />
              {t('dashboard.server.title')}
            </CardTitle>
            <CardDescription>
              {server ? t('dashboard.server.description', { uptime: formatUptime(t, server.uptime_seconds), cpu: server.cpu_count }) : t('dashboard.server.unavailable')}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {server ? (
              <>
                <MetricBar
                  label={t('dashboard.server.cpu')}
                  used={`${server.cpu_percent.toFixed(1)}%`}
                  total="100%"
                  percent={server.cpu_percent}
                  icon={Cpu}
                />
                <MetricBar
                  label={t('dashboard.server.memory')}
                  used={`${(server.memory_used_mb / 1024).toFixed(2)} GB`}
                  total={`${(server.memory_total_mb / 1024).toFixed(2)} GB`}
                  percent={server.memory_percent}
                  icon={Server}
                />
                <MetricBar
                  label={t('dashboard.server.disk')}
                  used={`${server.disk_used_gb} GB`}
                  total={`${server.disk_total_gb} GB`}
                  percent={server.disk_percent}
                  icon={HardDrive}
                />
              </>
            ) : (
              <p className="text-sm text-muted-foreground">{t('dashboard.server.noPsutil')}</p>
            )}
          </CardContent>
        </Card>

        {/* Database card */}
        <Card variant="glass">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Database className="h-5 w-5" />
              {t('dashboard.database.title')}
              {database.connected ? (
                <Badge variant="success">{t('dashboard.database.connected')}</Badge>
              ) : (
                <Badge variant="destructive">{t('dashboard.database.offline')}</Badge>
              )}
            </CardTitle>
            <CardDescription>
              {t('dashboard.database.description', { engine: database.engine, host: database.host, port: database.port, name: database.name, size: database.size_pretty ?? '—' })}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="text-sm text-muted-foreground mb-2">{t('dashboard.database.topTables')}</div>
            <div className="space-y-1">
              {database.tables.length === 0 && <p className="text-sm text-muted-foreground">{t('dashboard.database.noTables')}</p>}
              {database.tables.map((tbl) => (
                <div key={tbl.name} className="flex items-center justify-between text-sm py-1 border-b border-border/40 last:border-0">
                  <span className="font-mono">{tbl.name}</span>
                  <span className="text-muted-foreground">
                    {t('dashboard.database.rows', { count: tbl.rows.toLocaleString(), size: tbl.size })}
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
              {t('dashboard.sandbox.title')}
            </CardTitle>
            <CardDescription>{t('dashboard.sandbox.description')}</CardDescription>
          </CardHeader>
          <CardContent>
            {sandbox.error ? (
              <p className="text-sm text-destructive">{sandbox.error}</p>
            ) : (
              <div className="space-y-3 text-sm">
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">{t('dashboard.sandbox.running')}</span>
                  {sandbox.running ? (
                    <Badge variant="success">{t('dashboard.sandbox.yes')}</Badge>
                  ) : (
                    <Badge variant="destructive">{t('dashboard.sandbox.no')}</Badge>
                  )}
                </div>
                {(() => {
                  const buckets: Array<{ name: string; available: number; busy: number }> = [];
                  const pools = (sandbox as Record<string, unknown>).pools as
                    | Record<string, { available?: number; busy?: number }>
                    | undefined;
                  if (pools) {
                    for (const [name, info] of Object.entries(pools)) {
                      buckets.push({
                        name,
                        available: info?.available ?? 0,
                        busy: info?.busy ?? 0,
                      });
                    }
                  }
                  // sqlite is reported as a top-level key
                  const sqlite = (sandbox as Record<string, unknown>).sqlite as
                    | { available?: number; busy?: number }
                    | undefined;
                  if (sqlite && !buckets.find((b) => b.name === 'sqlite')) {
                    buckets.push({
                      name: 'sqlite',
                      available: sqlite.available ?? 0,
                      busy: sqlite.busy ?? 0,
                    });
                  }
                  if (buckets.length === 0) {
                    return <p className="text-xs text-muted-foreground">{t('dashboard.sandbox.noData')}</p>;
                  }
                  return (
                    <div className="grid gap-2 sm:grid-cols-2">
                      {buckets.map((b) => (
                        <div key={b.name} className="rounded-md border border-border/60 px-3 py-2 flex items-center justify-between">
                          <span className="font-mono text-xs uppercase">{b.name}</span>
                          <span className="text-xs text-muted-foreground">
                            <span className="text-foreground">{b.available}</span> {t('dashboard.sandbox.availability', { busy: b.busy })}
                          </span>
                        </div>
                      ))}
                    </div>
                  );
                })()}
              </div>
            )}
          </CardContent>
        </Card>

        {/* User breakdown */}
        <Card variant="glass">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Users className="h-5 w-5" />
              {t('dashboard.roles.title')}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <div className="flex items-center justify-between border-b border-border/40 pb-2">
              <span>{t('dashboard.roles.admins')}</span>
              <Badge variant="outline">{stats.users.admins}</Badge>
            </div>
            <div className="flex items-center justify-between border-b border-border/40 pb-2">
              <span>{t('dashboard.roles.instructors')}</span>
              <Badge variant="outline">{stats.users.instructors}</Badge>
            </div>
            <div className="flex items-center justify-between border-b border-border/40 pb-2">
              <span>{t('dashboard.roles.students')}</span>
              <Badge variant="outline">{stats.users.students}</Badge>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">{t('dashboard.roles.active24h')}</span>
              <Badge>{stats.users.active_24h}</Badge>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Recent activity */}
      <div className="grid gap-4 lg:grid-cols-2">
        <Card variant="glass">
          <CardHeader>
            <CardTitle>{t('dashboard.recentUsers.title')}</CardTitle>
          </CardHeader>
          <CardContent>
            {activity.recent_users.length === 0 ? (
              <p className="text-sm text-muted-foreground">{t('dashboard.recentUsers.empty')}</p>
            ) : (
              <div className="space-y-1">
                {activity.recent_users.map((u) => (
                  <div key={u.id} className="flex items-center justify-between text-sm py-1 border-b border-border/40 last:border-0">
                    <div>
                      <div className="font-medium">{u.full_name || '—'}</div>
                      <div className="text-xs text-muted-foreground">{u.email}</div>
                    </div>
                    <div className="text-right">
                      <Badge variant="outline" className="text-xs">{u.role}</Badge>
                      <div className="text-xs text-muted-foreground mt-0.5">
                        {u.last_login ? t('dashboard.recentUsers.seen', { when: formatRelative(t, u.last_login) }) : t('dashboard.recentUsers.neverLoggedIn')}
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
            <CardTitle>{t('dashboard.recentSubmissions.title')}</CardTitle>
          </CardHeader>
          <CardContent>
            {activity.recent_submissions.length === 0 ? (
              <p className="text-sm text-muted-foreground">{t('dashboard.recentSubmissions.empty')}</p>
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
                        <Badge variant="success" className="text-xs">{t('dashboard.recentSubmissions.correct')}</Badge>
                      ) : (
                        <Badge variant="destructive" className="text-xs">{t('dashboard.recentSubmissions.wrong')}</Badge>
                      )}
                      <div className="text-xs text-muted-foreground mt-0.5">{formatRelative(t, s.submitted_at)}</div>
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
