import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { adminApi } from '@/api/auth';
import type { AdminCreateUserData } from '@/api/auth';
import { useCourses } from '@/hooks/queries/useCourses';
import { getApiErrorMessage } from '@/lib/utils';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Spinner } from '@/components/ui/spinner';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog';
import {
  UserPlus,
  Search,
  Copy,
  Check,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';

export function UserManagementPage() {
  const { t } = useTranslation(['admin', 'common', 'auth']);
  const queryClient = useQueryClient();

  // Create user form state
  const [email, setEmail] = useState('');
  const [role, setRole] = useState<string>('');
  const [courseId, setCourseId] = useState<string>('');
  const [createError, setCreateError] = useState<string | null>(null);

  // Password dialog state
  const [passwordDialog, setPasswordDialog] = useState(false);
  const [createdEmail, setCreatedEmail] = useState('');
  const [createdPassword, setCreatedPassword] = useState('');
  const [copied, setCopied] = useState(false);

  // Users list state
  const [searchQuery, setSearchQuery] = useState('');
  const [roleFilter, setRoleFilter] = useState<string>('all');
  const [page, setPage] = useState(1);
  const pageSize = 20;

  const { data: coursesData } = useCourses();
  const courses = coursesData?.results ?? [];

  const usersQuery = useQuery({
    queryKey: ['admin-users', roleFilter, searchQuery, page],
    queryFn: () =>
      adminApi.listUsers({
        role: roleFilter === 'all' ? undefined : roleFilter,
        search: searchQuery || undefined,
        page,
        page_size: pageSize,
      }),
  });

  const getCredentialsText = (emailVal: string, passwordVal: string) => {
    const loginLabel = t('admin:userManagement.copyLoginLabel');
    const passwordLabel = t('admin:userManagement.copyPasswordLabel');
    return `${loginLabel}: ${emailVal}\n${passwordLabel}: ${passwordVal}`;
  };

  const createUserMutation = useMutation({
    mutationFn: (data: AdminCreateUserData) => adminApi.createUser(data),
    onSuccess: (response) => {
      setCreatedEmail(response.user.email);
      setCreatedPassword(response.password);
      setPasswordDialog(true);
      setCopied(false);

      // Auto-copy credentials
      const text = getCredentialsText(response.user.email, response.password);
      navigator.clipboard.writeText(text).then(() => {
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      });

      // Reset form
      setEmail('');
      setRole('');
      setCourseId('');
      setCreateError(null);

      queryClient.invalidateQueries({ queryKey: ['admin-users'] });
    },
    onError: (error) => {
      setCreateError(getApiErrorMessage(error, 'Failed to create user'));
    },
  });

  const handleCreateUser = () => {
    setCreateError(null);
    if (!email || !role) return;

    const data: AdminCreateUserData = {
      email,
      role: role as 'student' | 'instructor' | 'admin',
    };
    if (courseId && courseId !== 'none') {
      data.course_id = courseId;
    }
    createUserMutation.mutate(data);
  };

  const handleCopyCredentials = () => {
    const text = getCredentialsText(createdEmail, createdPassword);
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  const users = usersQuery.data?.results ?? [];
  const totalCount = usersQuery.data?.count ?? 0;
  const hasNext = !!usersQuery.data?.next;
  const hasPrev = !!usersQuery.data?.previous;

  return (
    <div className="space-y-6 animate-fade-in">
      <div>
        <h1 className="text-3xl font-bold">{t('admin:userManagement.title')}</h1>
        <p className="text-muted-foreground">{t('admin:userManagement.subtitle')}</p>
      </div>

      {/* Create User Card */}
      <Card variant="glass">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <UserPlus className="h-5 w-5" />
            {t('admin:userManagement.createUser')}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {createError && (
            <Alert variant="destructive" className="rounded-xl">
              <AlertDescription>{createError}</AlertDescription>
            </Alert>
          )}
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <div className="space-y-2">
              <Label>{t('admin:userManagement.email')}</Label>
              <Input
                type="email"
                placeholder={t('admin:userManagement.emailPlaceholder')}
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="h-10"
              />
            </div>
            <div className="space-y-2">
              <Label>{t('admin:userManagement.role')}</Label>
              <Select value={role} onValueChange={setRole}>
                <SelectTrigger className="h-10">
                  <SelectValue placeholder={t('admin:userManagement.selectRole')} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="student">Student</SelectItem>
                  <SelectItem value="instructor">Instructor</SelectItem>
                  <SelectItem value="admin">Admin</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>{t('admin:userManagement.course')}</Label>
              <Select value={courseId} onValueChange={setCourseId}>
                <SelectTrigger className="h-10">
                  <SelectValue placeholder={t('admin:userManagement.selectCourse')} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">{t('admin:userManagement.noCourse')}</SelectItem>
                  {courses.map((course) => (
                    <SelectItem key={course.id} value={course.id}>
                      {course.title}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label className="invisible">Action</Label>
              <Button
                onClick={handleCreateUser}
                disabled={!email || !role || createUserMutation.isPending}
                className="w-full h-10"
              >
                {createUserMutation.isPending ? (
                  <Spinner size="sm" className="mr-2" />
                ) : (
                  <UserPlus className="h-4 w-4 mr-2" />
                )}
                {t('admin:userManagement.createUserButton')}
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Users List Card */}
      <Card variant="glass">
        <CardHeader>
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <CardTitle>
              {t('admin:userManagement.usersList')}
              {totalCount > 0 && (
                <span className="ml-2 text-sm font-normal text-muted-foreground">
                  ({t('admin:userManagement.usersCount', { count: totalCount })})
                </span>
              )}
            </CardTitle>
            <div className="relative w-full sm:w-64">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder={t('admin:userManagement.searchPlaceholder')}
                value={searchQuery}
                onChange={(e) => {
                  setSearchQuery(e.target.value);
                  setPage(1);
                }}
                className="pl-9 h-10"
              />
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <Tabs
            value={roleFilter}
            onValueChange={(v) => {
              setRoleFilter(v);
              setPage(1);
            }}
          >
            <TabsList>
              <TabsTrigger value="all">{t('admin:userManagement.filterAll')}</TabsTrigger>
              <TabsTrigger value="student">{t('admin:userManagement.filterStudent')}</TabsTrigger>
              <TabsTrigger value="instructor">{t('admin:userManagement.filterInstructor')}</TabsTrigger>
              <TabsTrigger value="admin">{t('admin:userManagement.filterAdmin')}</TabsTrigger>
            </TabsList>
          </Tabs>

          {usersQuery.isLoading ? (
            <div className="flex justify-center py-8">
              <Spinner size="lg" />
            </div>
          ) : users.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              {searchQuery || roleFilter !== 'all'
                ? t('admin:userManagement.noUsers')
                : t('admin:userManagement.noUsersYet')}
            </div>
          ) : (
            <div className="space-y-2">
              {users.map((user) => (
                <div
                  key={user.id}
                  className="flex items-center gap-4 p-3 rounded-xl bg-secondary/30 hover:bg-secondary/50 transition-colors"
                >
                  {/* Avatar */}
                  {user.avatar_url ? (
                    <img
                      src={user.avatar_url}
                      alt={user.full_name}
                      className="h-10 w-10 rounded-full object-cover shrink-0"
                    />
                  ) : (
                    <div className="h-10 w-10 rounded-full bg-primary/10 flex items-center justify-center shrink-0">
                      <span className="text-sm font-semibold text-primary">
                        {user.first_name?.[0] || user.email[0].toUpperCase()}
                      </span>
                    </div>
                  )}

                  {/* Name & Email */}
                  <div className="flex-1 min-w-0">
                    <p className="font-medium truncate text-sm">
                      {user.full_name || user.email}
                    </p>
                    {user.full_name && (
                      <p className="text-xs text-muted-foreground truncate">{user.email}</p>
                    )}
                  </div>

                  {/* Badges */}
                  <div className="flex items-center gap-2 shrink-0">
                    <Badge
                      variant={
                        user.role === 'admin'
                          ? 'destructive'
                          : user.role === 'instructor'
                            ? 'default'
                            : 'secondary'
                      }
                    >
                      {user.role}
                    </Badge>
                    {user.must_change_password && (
                      <Badge variant="warning">
                        {t('admin:userManagement.mustChangePassword')}
                      </Badge>
                    )}
                  </div>

                  {/* Created date */}
                  <span className="text-xs text-muted-foreground shrink-0 hidden sm:block">
                    {new Date(user.created_at).toLocaleDateString()}
                  </span>
                </div>
              ))}
            </div>
          )}

          {/* Pagination */}
          {totalCount > pageSize && (
            <div className="flex items-center justify-center gap-2 pt-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage((p) => p - 1)}
                disabled={!hasPrev}
              >
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <span className="text-sm text-muted-foreground">
                {page}
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage((p) => p + 1)}
                disabled={!hasNext}
              >
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Password Created Dialog */}
      <Dialog open={passwordDialog} onOpenChange={setPasswordDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('admin:userManagement.passwordGenerated')}</DialogTitle>
            <DialogDescription>
              {t('admin:userManagement.passwordInstructions')}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>{t('admin:userManagement.email')}</Label>
              <Input value={createdEmail} readOnly className="h-10" />
            </div>
            <div className="space-y-2">
              <Label>{t('auth:fields.password')}</Label>
              <div className="flex gap-2">
                <Input
                  value={createdPassword}
                  readOnly
                  className="h-10 font-mono"
                />
                <Button
                  variant="outline"
                  size="icon"
                  className="h-10 w-10 shrink-0"
                  onClick={handleCopyCredentials}
                >
                  {copied ? (
                    <Check className="h-4 w-4 text-success" />
                  ) : (
                    <Copy className="h-4 w-4" />
                  )}
                </Button>
              </div>
              {copied && (
                <p className="text-xs text-success">{t('admin:userManagement.passwordCopied')}</p>
              )}
            </div>
          </div>
          <DialogFooter>
            <Button onClick={() => setPasswordDialog(false)}>OK</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
