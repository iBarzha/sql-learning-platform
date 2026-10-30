import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { AdminCreateUserData } from '@/api/auth';
import type { User } from '@/types';
import { useAuthStore } from '@/store/authStore';
import { useCourses } from '@/hooks/queries/useCourses';
import {
  useAdminUsers,
  useAvailableCourses,
  useCreateUser,
  useDeleteUser,
  useResetUserPassword,
  useUpdateUser,
} from '@/hooks/queries/useAdminUsers';
import { getApiErrorMessage } from '@/lib/utils';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Spinner } from '@/components/ui/spinner';
import { Switch } from '@/components/ui/switch';
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
  KeyRound,
  Trash2,
} from 'lucide-react';

type Role = User['role'];

const ROLES: Role[] = ['student', 'instructor', 'admin'];

function useCopy() {
  const [copied, setCopied] = useState(false);
  const copy = (text: string) =>
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  return { copied, copy, reset: () => setCopied(false) };
}

export function UserManagementPage() {
  const { t } = useTranslation(['admin', 'common', 'auth']);
  const currentUser = useAuthStore((s) => s.user);

  // Create user form state
  const [email, setEmail] = useState('');
  const [role, setRole] = useState<string>('');
  const [courseId, setCourseId] = useState<string>('');
  const [createError, setCreateError] = useState<string | null>(null);

  // Credentials dialog (used both for created users and password resets)
  const [credentials, setCredentials] = useState<{
    title: string;
    description: string;
    email: string;
    password: string;
  } | null>(null);
  const credentialsCopy = useCopy();

  // Delete confirmation
  const [userToDelete, setUserToDelete] = useState<User | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  // Users list state
  const [searchQuery, setSearchQuery] = useState('');
  const [roleFilter, setRoleFilter] = useState<string>('all');
  const [page, setPage] = useState(1);
  const pageSize = 20;

  const { data: coursesData } = useCourses();
  const { data: availableCourses = [] } = useAvailableCourses();
  const courses = [...(coursesData?.results ?? []), ...availableCourses].filter(
    (course, i, all) => all.findIndex((c) => c.id === course.id) === i
  );

  const usersQuery = useAdminUsers({
    role: roleFilter === 'all' ? undefined : roleFilter,
    search: searchQuery || undefined,
    page,
    page_size: pageSize,
  });

  const createUserMutation = useCreateUser();
  const updateUserMutation = useUpdateUser();
  const resetPasswordMutation = useResetUserPassword();
  const deleteUserMutation = useDeleteUser();

  const roleLabel = (value: Role) =>
    value === 'admin'
      ? t('admin:userManagement.roleAdmin')
      : value === 'instructor'
        ? t('admin:userManagement.roleInstructor')
        : t('admin:userManagement.roleStudent');

  const getCredentialsText = (emailVal: string, passwordVal: string) => {
    const loginLabel = t('admin:userManagement.copyLoginLabel');
    const passwordLabel = t('admin:userManagement.copyPasswordLabel');
    return `${loginLabel}: ${emailVal}\n${passwordLabel}: ${passwordVal}`;
  };

  const showCredentials = (title: string, description: string, emailVal: string, password: string) => {
    setCredentials({ title, description, email: emailVal, password });
    credentialsCopy.reset();
    credentialsCopy.copy(getCredentialsText(emailVal, password));
  };

  const handleCreateUser = () => {
    setCreateError(null);
    if (!email || !role) return;

    const data: AdminCreateUserData = {
      email,
      role: role as Role,
    };
    if (courseId && courseId !== 'none') {
      data.course_id = courseId;
    }
    createUserMutation.mutate(data, {
      onSuccess: (response) => {
        showCredentials(
          t('admin:userManagement.passwordGenerated'),
          t('admin:userManagement.passwordInstructions'),
          response.user.email,
          response.password
        );
        setEmail('');
        setRole('');
        setCourseId('');
      },
      onError: (error) => setCreateError(getApiErrorMessage(error, t('admin:userManagement.actionFailed'))),
    });
  };

  const handleRoleChange = (user: User, value: string) => {
    // Radix Select emits '' when its controlled value changes from outside.
    if (!value || value === user.role) return;
    setActionError(null);
    updateUserMutation.mutate(
      { id: user.id, data: { role: value as Role } },
      { onError: (error) => setActionError(getApiErrorMessage(error, t('admin:userManagement.actionFailed'))) }
    );
  };

  const handleActiveChange = (user: User, active: boolean) => {
    setActionError(null);
    updateUserMutation.mutate(
      { id: user.id, data: { is_active: active } },
      { onError: (error) => setActionError(getApiErrorMessage(error, t('admin:userManagement.actionFailed'))) }
    );
  };

  const handleResetPassword = (user: User) => {
    setActionError(null);
    resetPasswordMutation.mutate(user.id, {
      onSuccess: (response) =>
        showCredentials(
          t('admin:userManagement.resetPasswordTitle'),
          t('admin:userManagement.resetPasswordInstructions'),
          response.user.email,
          response.temporary_password
        ),
      onError: (error) => setActionError(getApiErrorMessage(error, t('admin:userManagement.actionFailed'))),
    });
  };

  const confirmDelete = () => {
    if (!userToDelete) return;
    setActionError(null);
    deleteUserMutation.mutate(userToDelete.id, {
      onSuccess: () => setUserToDelete(null),
      onError: (error) => {
        setUserToDelete(null);
        setActionError(getApiErrorMessage(error, t('admin:userManagement.actionFailed')));
      },
    });
  };

  const users = usersQuery.data?.results ?? [];
  const totalCount = usersQuery.data?.count ?? 0;
  const hasNext = !!usersQuery.data?.next;
  const hasPrev = !!usersQuery.data?.previous;
  const busy = updateUserMutation.isPending || resetPasswordMutation.isPending || deleteUserMutation.isPending;

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
              <Select value={role} onValueChange={(val) => val && setRole(val)}>
                <SelectTrigger className="h-10">
                  <SelectValue placeholder={t('admin:userManagement.selectRole')} />
                </SelectTrigger>
                <SelectContent>
                  {ROLES.map((value) => (
                    <SelectItem key={value} value={value}>
                      {roleLabel(value)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            {courses.length > 0 && (
              <div className="space-y-2">
                <Label>{t('admin:userManagement.course')}</Label>
                <Select value={courseId} onValueChange={(val) => val && setCourseId(val)}>
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
            )}
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
          {actionError && (
            <Alert variant="destructive" className="rounded-xl">
              <AlertDescription>{actionError}</AlertDescription>
            </Alert>
          )}

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
              {users.map((user) => {
                const isSelf = currentUser?.id === user.id;
                const hasName = Boolean(user.first_name || user.last_name);
                return (
                  <div
                    key={user.id}
                    className={`flex flex-wrap items-center gap-3 p-3 rounded-xl bg-secondary/30 hover:bg-secondary/50 transition-colors ${
                      user.is_active ? '' : 'opacity-60'
                    }`}
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
                    <div className="flex-1 min-w-[12rem]">
                      <p className="font-medium truncate text-sm">
                        {hasName ? user.full_name : t('admin:userManagement.noName')}
                        {isSelf && (
                          <span className="ml-2 text-xs font-normal text-muted-foreground">
                            ({t('admin:userManagement.you')})
                          </span>
                        )}
                      </p>
                      <p className="text-xs text-muted-foreground truncate">{user.email}</p>
                      <p className="text-xs text-muted-foreground hidden sm:block">
                        {t('admin:userManagement.lastLogin')}:{' '}
                        {user.last_login
                          ? new Date(user.last_login).toLocaleString()
                          : t('admin:userManagement.neverLoggedIn')}
                      </p>
                    </div>

                    {/* Badges */}
                    <div className="flex items-center gap-2 shrink-0">
                      {user.must_change_password && (
                        <Badge variant="warning">
                          {t('admin:userManagement.mustChangePassword')}
                        </Badge>
                      )}
                      {!user.is_active && (
                        <Badge variant="destructive">{t('admin:userManagement.inactive')}</Badge>
                      )}
                    </div>

                    {/* Actions */}
                    <div className="flex items-center gap-2 shrink-0">
                      <Select
                        value={user.role}
                        onValueChange={(val) => handleRoleChange(user, val)}
                        disabled={isSelf || busy}
                      >
                        <SelectTrigger className="h-9 w-32" aria-label={t('admin:userManagement.role')}>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {ROLES.map((value) => (
                            <SelectItem key={value} value={value}>
                              {roleLabel(value)}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>

                      <label className="flex items-center gap-2 text-xs text-muted-foreground">
                        <Switch
                          checked={user.is_active}
                          disabled={isSelf || busy}
                          onCheckedChange={(checked) => handleActiveChange(user, checked)}
                          aria-label={t('admin:userManagement.active')}
                        />
                        <span className="hidden md:inline">
                          {user.is_active
                            ? t('admin:userManagement.active')
                            : t('admin:userManagement.inactive')}
                        </span>
                      </label>

                      <Button
                        variant="outline"
                        size="sm"
                        disabled={busy}
                        onClick={() => handleResetPassword(user)}
                        title={t('admin:userManagement.resetPassword')}
                        aria-label={t('admin:userManagement.resetPassword')}
                      >
                        <KeyRound className="h-4 w-4" />
                        <span className="hidden lg:inline ml-1">
                          {t('admin:userManagement.resetPassword')}
                        </span>
                      </Button>

                      <Button
                        variant="ghost"
                        size="icon"
                        className="text-destructive hover:text-destructive"
                        disabled={isSelf || busy}
                        onClick={() => setUserToDelete(user)}
                        title={t('admin:userManagement.deleteUser')}
                        aria-label={t('admin:userManagement.deleteUser')}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                );
              })}
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
                aria-label={t('common:previous', { defaultValue: 'Previous' })}
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
                aria-label={t('common:next', { defaultValue: 'Next' })}
              >
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Credentials Dialog (created user / password reset) */}
      <Dialog open={!!credentials} onOpenChange={(open) => !open && setCredentials(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{credentials?.title}</DialogTitle>
            <DialogDescription>{credentials?.description}</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>{t('admin:userManagement.email')}</Label>
              <Input value={credentials?.email ?? ''} readOnly className="h-10" />
            </div>
            <div className="space-y-2">
              <Label>{t('admin:userManagement.temporaryPassword')}</Label>
              <div className="flex gap-2">
                <Input
                  value={credentials?.password ?? ''}
                  readOnly
                  className="h-10 font-mono"
                />
                <Button
                  variant="outline"
                  size="icon"
                  className="h-10 w-10 shrink-0"
                  aria-label={t('admin:userManagement.copyPassword')}
                  onClick={() =>
                    credentials && credentialsCopy.copy(getCredentialsText(credentials.email, credentials.password))
                  }
                >
                  {credentialsCopy.copied ? (
                    <Check className="h-4 w-4 text-success" />
                  ) : (
                    <Copy className="h-4 w-4" />
                  )}
                </Button>
              </div>
              {credentialsCopy.copied && (
                <p className="text-xs text-success">{t('admin:userManagement.passwordCopied')}</p>
              )}
            </div>
          </div>
          <DialogFooter>
            <Button onClick={() => setCredentials(null)}>OK</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete confirmation */}
      <Dialog open={!!userToDelete} onOpenChange={(open) => !open && setUserToDelete(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('admin:userManagement.deleteUserTitle')}</DialogTitle>
            <DialogDescription>
              {t('admin:userManagement.deleteUserConfirm', { email: userToDelete?.email ?? '' })}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setUserToDelete(null)}>
              {t('admin:userManagement.cancel')}
            </Button>
            <Button
              variant="destructive"
              onClick={confirmDelete}
              disabled={deleteUserMutation.isPending}
            >
              {deleteUserMutation.isPending ? <Spinner size="sm" className="mr-2" /> : null}
              {t('admin:userManagement.confirmDelete')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
