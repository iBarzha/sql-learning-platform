import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { useTranslation } from 'react-i18next';
import { useAuthStore } from '@/store/authStore';
import authApi from '@/api/auth';
import { getApiErrorMessage } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Spinner } from '@/components/ui/spinner';
import { changePasswordSchema, type ChangePasswordFormData } from '@/lib/schemas';

export function ChangePasswordPage() {
  const { t } = useTranslation(['auth', 'common']);
  const navigate = useNavigate();
  const { user, fetchUser } = useAuthStore();

  const [isLoading, setIsLoading] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);

  const mustChangePassword = user?.must_change_password;

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<ChangePasswordFormData>({
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    resolver: zodResolver(changePasswordSchema) as any,
    defaultValues: {
      old_password: '',
      new_password: '',
      new_password_confirm: '',
    },
  });

  const onSubmit = async (data: ChangePasswordFormData) => {
    setApiError(null);
    setIsLoading(true);

    try {
      if (mustChangePassword) {
        await authApi.setPassword({
          new_password: data.new_password,
          new_password_confirm: data.new_password_confirm,
        });
      } else {
        await authApi.changePassword(data);
      }

      await fetchUser();
      navigate('/', { replace: true });
    } catch (err) {
      setApiError(getApiErrorMessage(err, t('auth:changePassword.error')));
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-background p-4">
      <div className="w-full max-w-md">
        <Card variant="glass" className="shadow-noble-lg animate-fade-in">
          <CardHeader className="space-y-1">
            <CardTitle className="text-2xl font-bold">
              {mustChangePassword
                ? t('auth:changePassword.setTitle')
                : t('auth:changePassword.title')}
            </CardTitle>
            <CardDescription>
              {mustChangePassword
                ? t('auth:changePassword.setSubtitle')
                : t('auth:changePassword.subtitle')}
            </CardDescription>
          </CardHeader>
          <form onSubmit={handleSubmit(onSubmit)}>
            <CardContent className="space-y-4">
              {apiError && (
                <Alert variant="destructive" className="rounded-xl">
                  <AlertDescription>{apiError}</AlertDescription>
                </Alert>
              )}
              {!mustChangePassword && (
                <div className="space-y-2">
                  <Label htmlFor="old_password">{t('auth:changePassword.currentPassword')}</Label>
                  <Input
                    id="old_password"
                    type="password"
                    {...register('old_password')}
                    required={!mustChangePassword}
                    autoComplete="current-password"
                    className="h-12"
                  />
                </div>
              )}
              <div className="space-y-2">
                <Label htmlFor="new_password">{t('auth:changePassword.newPassword')}</Label>
                <Input
                  id="new_password"
                  type="password"
                  {...register('new_password')}
                  autoComplete="new-password"
                  className="h-12"
                />
                {errors.new_password && (
                  <p className="text-sm text-destructive">{errors.new_password.message}</p>
                )}
              </div>
              <div className="space-y-2">
                <Label htmlFor="new_password_confirm">{t('auth:changePassword.confirmNewPassword')}</Label>
                <Input
                  id="new_password_confirm"
                  type="password"
                  {...register('new_password_confirm')}
                  autoComplete="new-password"
                  className="h-12"
                />
                {errors.new_password_confirm && (
                  <p className="text-sm text-destructive">{errors.new_password_confirm.message}</p>
                )}
              </div>
            </CardContent>
            <CardFooter>
              <Button type="submit" className="w-full h-12" disabled={isLoading}>
                {isLoading ? <Spinner size="sm" className="mr-2" /> : null}
                {mustChangePassword
                  ? t('auth:changePassword.setSubmit')
                  : t('auth:changePassword.submit')}
              </Button>
            </CardFooter>
          </form>
        </Card>
      </div>
    </div>
  );
}

export default ChangePasswordPage;
