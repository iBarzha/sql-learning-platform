import { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { useTranslation } from 'react-i18next';
import { useAuthStore } from '@/store/authStore';
import { getApiErrorMessage } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Spinner } from '@/components/ui/spinner';
import { AuthLayout } from '@/components/auth/AuthLayout';
import { loginSchema, type LoginFormData } from '@/lib/schemas';

export function LoginPage() {
  const { t } = useTranslation(['auth', 'common']);
  const navigate = useNavigate();
  const location = useLocation();
  const { login } = useAuthStore();

  const [isLoading, setIsLoading] = useState(false);
  const [loginError, setLoginError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginFormData>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: '', password: '' },
  });

  const from = (location.state as { from?: { pathname: string } })?.from?.pathname || '/';

  const onSubmit = async (data: LoginFormData) => {
    setLoginError(null);
    setIsLoading(true);
    try {
      await login(data);
      navigate(from, { replace: true });
    } catch (err) {
      setLoginError(getApiErrorMessage(err, t('auth:login.error', 'Invalid credentials')));
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <AuthLayout mobileTaglineKey="auth:branding.tagline">
      <Card variant="glass" className="shadow-noble-lg animate-fade-in">
        <CardHeader className="space-y-1 pb-4">
          <CardTitle className="text-2xl">{t('auth:login.title')}</CardTitle>
          <CardDescription>
            {t('auth:login.subtitle')}
          </CardDescription>
        </CardHeader>
        <form onSubmit={handleSubmit(onSubmit)}>
          <CardContent className="space-y-4">
            {loginError && (
              <Alert variant="destructive" className="rounded-xl">
                <AlertDescription>{loginError}</AlertDescription>
              </Alert>
            )}
            <div className="space-y-2">
              <Label htmlFor="email">{t('auth:fields.email')}</Label>
              <Input
                id="email"
                type="email"
                placeholder={t('auth:fields.emailPlaceholder')}
                {...register('email')}
                autoComplete="email"
                className="h-12"
              />
              {errors.email && (
                <p className="text-sm text-destructive">{errors.email.message}</p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">{t('auth:fields.password')}</Label>
              <Input
                id="password"
                type="password"
                {...register('password')}
                autoComplete="current-password"
                className="h-12"
              />
              {errors.password && (
                <p className="text-sm text-destructive">{errors.password.message}</p>
              )}
            </div>
          </CardContent>
          <CardFooter className="flex flex-col space-y-4 pt-2">
            <Button type="submit" className="w-full h-12" disabled={isLoading}>
              {isLoading ? <Spinner size="sm" className="mr-2" /> : null}
              {t('auth:login.submit')}
            </Button>
          </CardFooter>
        </form>
      </Card>
    </AuthLayout>
  );
}

export default LoginPage;
