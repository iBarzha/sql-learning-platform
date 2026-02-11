import { useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { QueryClientProvider } from '@tanstack/react-query';
import { queryClient } from '@/lib/queryClient';
import { useAuthStore } from '@/store/authStore';
import { usePreferencesStore } from '@/store/preferencesStore';
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { MainLayout } from '@/components/layout';
import { LoginPage, ChangePasswordPage } from '@/pages/auth';
import { DashboardPage } from '@/pages/dashboard';
import { CoursesListPage, CourseDetailPage } from '@/pages/courses';
import { LessonPage } from '@/pages/lessons';
import { AssignmentPage } from '@/pages/assignments';
import { ProfilePage } from '@/pages/profile';
import { SandboxPage } from '@/pages/sandbox';
import {
  MyCoursesPage,
  CourseFormPage,
  CourseManagePage,
  LessonFormPage,
  StudentsPage,
  AllStudentsPage,
} from '@/pages/instructor';
import { SettingsPage, UserManagementPage } from '@/pages/admin';
import { Spinner } from '@/components/ui/spinner';

function AppRoutes() {
  const { isAuthenticated, isLoading, fetchUser, user } = useAuthStore();
  const { t, i18n } = useTranslation();
  const locale = usePreferencesStore((s) => s.locale);

  useEffect(() => {
    fetchUser();
  }, [fetchUser]);

  // Sync document title and html lang attribute when language changes
  useEffect(() => {
    document.title = t('common:branding.fullName');
    document.documentElement.lang = i18n.language;
  }, [locale, i18n.language, t]);

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Spinner size="lg" />
      </div>
    );
  }

  const isInstructor = user?.role === 'instructor' || user?.role === 'admin';
  const isAdmin = user?.role === 'admin';

  return (
    <Routes>
      {/* Public routes */}
      <Route
        path="/login"
        element={isAuthenticated ? <Navigate to="/" replace /> : <LoginPage />}
      />

      {/* Protected routes with layout */}
      <Route
        element={
          <ProtectedRoute>
            <MainLayout />
          </ProtectedRoute>
        }
      >
        {/* Common routes */}
        <Route index element={<DashboardPage />} />
        <Route path="courses" element={<CoursesListPage />} />
        <Route path="courses/:courseId" element={<CourseDetailPage />} />
        <Route path="courses/:courseId/lessons/:lessonId" element={<LessonPage />} />
        <Route path="courses/:courseId/assignments/:assignmentId" element={<AssignmentPage />} />
        <Route path="sandbox" element={<SandboxPage />} />
        <Route path="profile" element={<ProfilePage />} />
        <Route path="change-password" element={<ChangePasswordPage />} />

        {/* Instructor routes */}
        <Route
          path="my-courses"
          element={isInstructor ? <MyCoursesPage /> : <Navigate to="/" replace />}
        />
        <Route
          path="courses/new"
          element={isInstructor ? <CourseFormPage /> : <Navigate to="/" replace />}
        />
        <Route
          path="courses/:courseId/edit"
          element={isInstructor ? <CourseFormPage /> : <Navigate to="/" replace />}
        />
        <Route
          path="courses/:courseId/manage"
          element={isInstructor ? <CourseManagePage /> : <Navigate to="/" replace />}
        />
        <Route
          path="courses/:courseId/lessons/new"
          element={isInstructor ? <LessonFormPage /> : <Navigate to="/" replace />}
        />
        <Route
          path="courses/:courseId/lessons/:lessonId/edit"
          element={isInstructor ? <LessonFormPage /> : <Navigate to="/" replace />}
        />
        <Route
          path="courses/:courseId/students"
          element={isInstructor ? <StudentsPage /> : <Navigate to="/" replace />}
        />
        <Route
          path="students"
          element={isInstructor ? <AllStudentsPage /> : <Navigate to="/" replace />}
        />

        {/* Admin routes */}
        <Route
          path="settings"
          element={isAdmin ? <SettingsPage /> : <Navigate to="/" replace />}
        />
        <Route
          path="users"
          element={isAdmin ? <UserManagementPage /> : <Navigate to="/" replace />}
        />
      </Route>

      {/* Catch all */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
