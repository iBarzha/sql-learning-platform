import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { useTranslation } from 'react-i18next';
import { useAuthStore } from '@/store/authStore';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Spinner } from '@/components/ui/spinner';
import { Progress } from '@/components/ui/progress';
import { AuthLayout } from '@/components/auth/AuthLayout';
import { registerSchema, type RegisterFormData } from '@/lib/schemas';

function getPasswordStrength(password: string): {
  value: number;
  variant: 'destructive' | 'warning' | 'success';
  label: string;
} {
  if (password.length === 0) return { value: 0, variant: 'destructive', label: '' };

  let score = 0;
  if (password.length >= 8) score += 1;
  if (password.length >= 12) score += 1;
  if (/[a-z]/.test(password) && /[A-Z]/.test(password)) score += 1;
  if (/\d/.test(password)) score += 1;
  if (/[^a-zA-Z0-9]/.test(password)) score += 1;

  if (score <= 1) return { value: 20, variant: 'destructive', label: 'weak' };
  if (score <= 2) return { value: 40, variant: 'destructive', label: 'weak' };
  if (score <= 3) return { value: 60, variant: 'warning', label: 'fair' };
  if (score <= 4) return { value: 80, variant: 'warning', label: 'good' };
  return { value: 100, variant: 'success', label: 'strong' };
}

export function RegisterPage() {
  const { t } = useTranslation(['auth', 'common']);
  const navigate = useNavigate();
  const { register: registerUser, isLoading, error, clearError } = useAuthStore();
  const [passwordValue, setPasswordValue] = useState('');

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<RegisterFormData>({
    resolver: zodResolver(registerSchema),
    defaultValues: {
      email: '',
      password: '',
      password_confirm: '',
      first_name: '',
      last_name: '',
    },
  });

  const onSubmit = async (data: RegisterFormData) => {
    clearError();
    try {
      await registerUser(data);
      navigate('/', { replace: true });
    } catch {
      // Error is handled in store
    }
  };

  const passwordStrength = getPasswordStrength(passwordValue);
  const passwordRegistration = register('password');

  return (
    <AuthLayout mobileTaglineKey="auth:branding.startJourney">
      <Card variant="glass" className="shadow-noble-lg animate-fade-in">
        <CardHeader className="space-y-1 pb-4">
          <CardTitle className="text-2xl">{t('auth:register.title')}</CardTitle>
          <CardDescription>
            {t('auth:register.subtitle')}
          </CardDescription>
        </CardHeader>
        <form onSubmit={handleSubmit(onSubmit)}>
          <CardContent className="space-y-4">
            {error && (
              <Alert variant="destructive" className="rounded-xl">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="first_name">{t('auth:fields.firstName')}</Label>
                <Input
                  id="first_name"
                  placeholder={t('auth:fields.firstNamePlaceholder')}
                  {...register('first_name')}
                  autoComplete="given-name"
                  className="h-12"
                />
                {errors.first_name && (
                  <p className="text-sm text-destructive">{errors.first_name.message}</p>
                )}
              </div>
              <div className="space-y-2">
                <Label htmlFor="last_name">{t('auth:fields.lastName')}</Label>
                <Input
                  id="last_name"
                  placeholder={t('auth:fields.lastNamePlaceholder')}
                  {...register('last_name')}
                  autoComplete="family-name"
                  className="h-12"
                />
                {errors.last_name && (
                  <p className="text-sm text-destructive">{errors.last_name.message}</p>
                )}
              </div>
            </div>
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
                {...passwordRegistration}
                onChange={(e) => {
                  passwordRegistration.onChange(e);
                  setPasswordValue(e.target.value);
                }}
                autoComplete="new-password"
                className="h-12"
              />
              {passwordValue.length > 0 && (
                <div className="space-y-1">
                  <Progress
                    value={passwordStrength.value}
                    variant={passwordStrength.variant}
                    className="h-1.5"
                  />
                  <p className={`text-xs ${
                    passwordStrength.variant === 'destructive'
                      ? 'text-destructive'
                      : passwordStrength.variant === 'warning'
                        ? 'text-warning'
                        : 'text-success'
                  }`}>
                    {t(`auth:register.passwordStrength.${passwordStrength.label}`)}
                  </p>
                </div>
              )}
              {errors.password && (
                <p className="text-sm text-destructive">{errors.password.message}</p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="password_confirm">{t('auth:fields.confirmPassword')}</Label>
              <Input
                id="password_confirm"
                type="password"
                {...register('password_confirm')}
                autoComplete="new-password"
                className="h-12"
              />
              {errors.password_confirm && (
                <p className="text-sm text-destructive">{errors.password_confirm.message}</p>
              )}
            </div>
          </CardContent>
          <CardFooter className="flex flex-col space-y-4 pt-2">
            <Button type="submit" className="w-full h-12" disabled={isLoading}>
              {isLoading ? <Spinner size="sm" className="mr-2" /> : null}
              {t('auth:register.submit')}
            </Button>
            <p className="text-sm text-muted-foreground text-center">
              {t('auth:register.hasAccount')}{' '}
              <Link to="/login" className="text-primary font-medium hover:underline">
                {t('auth:register.signInLink')}
              </Link>
            </p>
          </CardFooter>
        </form>
      </Card>
    </AuthLayout>
  );
}

export default RegisterPage;
