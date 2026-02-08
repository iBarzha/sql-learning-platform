import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
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
    resolver: zodResolver(changePasswordSchema),
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
      setApiError(getApiErrorMessage(err, 'Failed to change password'));
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-background p-4">
      <Card className="w-full max-w-md">
        <CardHeader className="space-y-1">
          <CardTitle className="text-2xl font-bold">
            {mustChangePassword ? 'Set your password' : 'Change password'}
          </CardTitle>
          <CardDescription>
            {mustChangePassword
              ? 'You must set a new password before continuing'
              : 'Enter your current and new password'}
          </CardDescription>
        </CardHeader>
        <form onSubmit={handleSubmit(onSubmit)}>
          <CardContent className="space-y-4">
            {apiError && (
              <Alert variant="destructive">
                <AlertDescription>{apiError}</AlertDescription>
              </Alert>
            )}
            {!mustChangePassword && (
              <div className="space-y-2">
                <Label htmlFor="old_password">Current password</Label>
                <Input
                  id="old_password"
                  type="password"
                  {...register('old_password')}
                  required={!mustChangePassword}
                  autoComplete="current-password"
                />
              </div>
            )}
            <div className="space-y-2">
              <Label htmlFor="new_password">New password</Label>
              <Input
                id="new_password"
                type="password"
                {...register('new_password')}
                autoComplete="new-password"
              />
              {errors.new_password && (
                <p className="text-sm text-destructive">{errors.new_password.message}</p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="new_password_confirm">Confirm new password</Label>
              <Input
                id="new_password_confirm"
                type="password"
                {...register('new_password_confirm')}
                autoComplete="new-password"
              />
              {errors.new_password_confirm && (
                <p className="text-sm text-destructive">{errors.new_password_confirm.message}</p>
              )}
            </div>
          </CardContent>
          <CardFooter>
            <Button type="submit" className="w-full" disabled={isLoading}>
              {isLoading ? <Spinner size="sm" className="mr-2" /> : null}
              {mustChangePassword ? 'Set password' : 'Change password'}
            </Button>
          </CardFooter>
        </form>
      </Card>
    </div>
  );
}

export default ChangePasswordPage;
