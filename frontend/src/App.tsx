import { useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { useAuthStore } from '@/store/authStore';
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { LoginPage, RegisterPage, ChangePasswordPage } from '@/pages/auth';
import { Spinner } from '@/components/ui/spinner';

function HomePage() {
  const { user, logout } = useAuthStore();

  return (
    <div className="min-h-screen bg-background p-8">
      <div className="max-w-4xl mx-auto">
        <div className="flex justify-between items-center mb-8">
          <h1 className="text-3xl font-bold">SQL Learning Platform</h1>
          <button
            onClick={() => logout()}
            className="px-4 py-2 text-sm text-muted-foreground hover:text-foreground"
          >
            Sign out
          </button>
        </div>
        <div className="bg-card rounded-lg border p-6">
          <h2 className="text-xl font-semibold mb-4">
            Welcome, {user?.full_name || user?.email}!
          </h2>
          <p className="text-muted-foreground mb-4">
            Role: <span className="capitalize">{user?.role}</span>
          </p>
          <p className="text-muted-foreground">
            Dashboard and course content will be added in the next phase.
          </p>
        </div>
      </div>
    </div>
  );
}

function AppRoutes() {
  const { isAuthenticated, isLoading, fetchUser } = useAuthStore();

  useEffect(() => {
    fetchUser();
  }, [fetchUser]);

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Spinner size="lg" />
      </div>
    );
  }

  return (
    <Routes>
      <Route
        path="/login"
        element={isAuthenticated ? <Navigate to="/" replace /> : <LoginPage />}
      />
      <Route
        path="/register"
        element={isAuthenticated ? <Navigate to="/" replace /> : <RegisterPage />}
      />
      <Route
        path="/change-password"
        element={
          <ProtectedRoute>
            <ChangePasswordPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <HomePage />
          </ProtectedRoute>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

function App() {
  return (
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  );
}

export default App;
