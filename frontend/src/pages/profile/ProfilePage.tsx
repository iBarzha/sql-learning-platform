import { useRef, useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { useAuthStore } from '@/store/authStore';
import { useMyProgress } from '@/hooks/queries/useSubmissions';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Spinner } from '@/components/ui/spinner';
import { Badge } from '@/components/ui/badge';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { User, Mail, Calendar, Shield, Key, Camera, GraduationCap } from 'lucide-react';
import { Link } from 'react-router-dom';

export function ProfilePage() {
  const { t } = useTranslation('profile');
  const { user, updateUser, uploadAvatar, isLoading, error, clearError } = useAuthStore();
  const [editing, setEditing] = useState(false);
  const [firstName, setFirstName] = useState(user?.first_name || '');
  const [lastName, setLastName] = useState(user?.last_name || '');
  const [success, setSuccess] = useState(false);
  const [avatarUploading, setAvatarUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const successTimerRef = useRef<ReturnType<typeof setTimeout>>(undefined);

  // Clear success timer on unmount
  useEffect(() => {
    return () => {
      if (successTimerRef.current) clearTimeout(successTimerRef.current);
    };
  }, []);

  const showSuccessMessage = useCallback(() => {
    setSuccess(true);
    if (successTimerRef.current) clearTimeout(successTimerRef.current);
    successTimerRef.current = setTimeout(() => setSuccess(false), 3000);
  }, []);

  const isStudent = user?.role === 'student';
  const { data: progress = [], isLoading: progressLoading } = useMyProgress();

  async function handleSave() {
    try {
      clearError();
      setSuccess(false);
      await updateUser({ first_name: firstName, last_name: lastName });
      setEditing(false);
      showSuccessMessage();
    } catch {
      // Error is handled in store
    }
  }

  function handleCancel() {
    setFirstName(user?.first_name || '');
    setLastName(user?.last_name || '');
    setEditing(false);
    clearError();
  }

  async function handleAvatarChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;

    setAvatarUploading(true);
    try {
      clearError();
      await uploadAvatar(file);
      showSuccessMessage();
    } catch {
      // Error handled in store
    } finally {
      setAvatarUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  }

  if (!user) return null;

  const initials = `${(user.first_name?.[0] ?? '').toUpperCase()}${(user.last_name?.[0] ?? '').toUpperCase()}`;

  return (
    <div className="max-w-2xl mx-auto space-y-6 animate-fade-in">
      <div className="flex items-center gap-4">
        <div className="relative group">
          <Avatar size="lg">
            {user.avatar_url ? (
              <AvatarImage src={user.avatar_url} alt={user.full_name} />
            ) : (
              <AvatarFallback size="lg">{initials}</AvatarFallback>
            )}
          </Avatar>
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={avatarUploading}
            className="absolute inset-0 flex items-center justify-center rounded-full bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity cursor-pointer"
          >
            {avatarUploading ? (
              <Spinner size="sm" className="text-white" />
            ) : (
              <Camera className="h-5 w-5 text-white" />
            )}
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/jpeg,image/png,image/webp,image/gif"
            onChange={handleAvatarChange}
            className="hidden"
          />
        </div>
        <div>
          <h1 className="text-3xl font-bold">{t('title')}</h1>
          <p className="text-muted-foreground">{t('subtitle')}</p>
        </div>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {success && (
        <Alert variant="success">
          <AlertDescription>{t('updateSuccess')}</AlertDescription>
        </Alert>
      )}

      <Card variant="glass">
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>{t('personalInfo.title')}</CardTitle>
              <CardDescription>{t('personalInfo.subtitle')}</CardDescription>
            </div>
            {!editing && (
              <Button variant="outline" onClick={() => setEditing(true)}>
                {t('personalInfo.edit')}
              </Button>
            )}
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {editing ? (
            <>
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="firstName">{t('personalInfo.firstName')}</Label>
                  <Input
                    id="firstName"
                    value={firstName}
                    onChange={(e) => setFirstName(e.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="lastName">{t('personalInfo.lastName')}</Label>
                  <Input
                    id="lastName"
                    value={lastName}
                    onChange={(e) => setLastName(e.target.value)}
                  />
                </div>
              </div>
              <div className="flex justify-end gap-2">
                <Button variant="outline" onClick={handleCancel}>
                  {t('personalInfo.cancel')}
                </Button>
                <Button onClick={handleSave} disabled={isLoading}>
                  {isLoading ? <Spinner size="sm" /> : t('personalInfo.save')}
                </Button>
              </div>
            </>
          ) : (
            <div className="space-y-4">
              <div className="flex items-center gap-3">
                <User className="h-4 w-4 text-muted-foreground" />
                <div>
                  <p className="text-sm text-muted-foreground">{t('personalInfo.fullName')}</p>
                  <p className="font-medium">{user.full_name}</p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <Mail className="h-4 w-4 text-muted-foreground" />
                <div>
                  <p className="text-sm text-muted-foreground">{t('personalInfo.email')}</p>
                  <p className="font-medium">{user.email}</p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <Shield className="h-4 w-4 text-muted-foreground" />
                <div>
                  <p className="text-sm text-muted-foreground">{t('personalInfo.role')}</p>
                  <Badge variant="outline" className="capitalize">
                    {user.role}
                  </Badge>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <Calendar className="h-4 w-4 text-muted-foreground" />
                <div>
                  <p className="text-sm text-muted-foreground">{t('personalInfo.memberSince')}</p>
                  <p className="font-medium">
                    {new Date(user.created_at).toLocaleDateString()}
                  </p>
                </div>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      <Card variant="glass">
        <CardHeader>
          <CardTitle>{t('security.title')}</CardTitle>
          <CardDescription>{t('security.subtitle')}</CardDescription>
        </CardHeader>
        <CardContent>
          <Link to="/change-password">
            <Button variant="outline" className="w-full sm:w-auto">
              <Key className="h-4 w-4 mr-2" />
              {t('security.changePassword')}
            </Button>
          </Link>
        </CardContent>
      </Card>

      {isStudent && (
        <Card variant="glass">
          <CardHeader>
            <CardTitle>{t('grades.title')}</CardTitle>
            <CardDescription>{t('grades.subtitle')}</CardDescription>
          </CardHeader>
          <CardContent>
            {progressLoading ? (
              <div className="flex justify-center py-8">
                <Spinner />
              </div>
            ) : progress.length === 0 ? (
              <div className="text-center py-8">
                <GraduationCap className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
                <h3 className="font-medium text-lg mb-2">{t('grades.noGrades')}</h3>
                <p className="text-muted-foreground">{t('grades.noGradesDesc')}</p>
              </div>
            ) : (
              <div className="space-y-4">
                {progress.map((cp) => (
                  <Link
                    key={cp.course_id}
                    to={`/courses/${cp.course_id}`}
                    className="block p-4 rounded-xl border border-border/50 hover:bg-muted/30 transition-colors"
                  >
                    <div className="flex items-center justify-between mb-2">
                      <h4 className="font-medium">{cp.course_title}</h4>
                      <Badge variant="outline">
                        {Math.round(cp.percentage_score)}%
                      </Badge>
                    </div>
                    <div className="flex items-center justify-between text-sm text-muted-foreground mb-2">
                      <span>
                        {t('grades.tasks', {
                          completed: cp.completed_assignments,
                          total: cp.total_assignments,
                        })}
                      </span>
                      <span>{Math.round(cp.completion_rate)}%</span>
                    </div>
                    <div className="h-2 rounded-full bg-muted overflow-hidden">
                      <div
                        className="h-full rounded-full bg-primary transition-all duration-300"
                        style={{ width: `${Math.min(cp.completion_rate, 100)}%` }}
                      />
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
