import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '@/store/authStore';
import authApi from '@/api/auth';
import { getApiErrorMessage } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Spinner } from '@/components/ui/spinner';

export function ChangePasswordPage() {
  const navigate = useNavigate();
  const { user, fetchUser } = useAuthStore();

  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [formData, setFormData] = useState({
    old_password: '',
    new_password: '',
    new_password_confirm: '',
  });

  const mustChangePassword = user?.must_change_password;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (formData.new_password !== formData.new_password_confirm) {
      setError('Passwords do not match');
      return;
    }

    if (formData.new_password.length < 8) {
      setError('Password must be at least 8 characters');
      return;
    }

    setIsLoading(true);

    try {
      if (mustChangePassword) {
        await authApi.setPassword({
          new_password: formData.new_password,
          new_password_confirm: formData.new_password_confirm,
        });
      } else {
        await authApi.changePassword(formData);
      }

      await fetchUser();
      navigate('/', { replace: true });
    } catch (err) {
      setError(getApiErrorMessage(err, 'Failed to change password'));
    } finally {
      setIsLoading(false);
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData((prev) => ({
      ...prev,
      [e.target.name]: e.target.value,
    }));
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
        <form onSubmit={handleSubmit}>
          <CardContent className="space-y-4">
            {error && (
              <Alert variant="destructive">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}
            {!mustChangePassword && (
              <div className="space-y-2">
                <Label htmlFor="old_password">Current password</Label>
                <Input
                  id="old_password"
                  name="old_password"
                  type="password"
                  value={formData.old_password}
                  onChange={handleChange}
                  required={!mustChangePassword}
                  autoComplete="current-password"
                />
              </div>
            )}
            <div className="space-y-2">
              <Label htmlFor="new_password">New password</Label>
              <Input
                id="new_password"
                name="new_password"
                type="password"
                value={formData.new_password}
                onChange={handleChange}
                required
                autoComplete="new-password"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="new_password_confirm">Confirm new password</Label>
              <Input
                id="new_password_confirm"
                name="new_password_confirm"
                type="password"
                value={formData.new_password_confirm}
                onChange={handleChange}
                required
                autoComplete="new-password"
              />
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
