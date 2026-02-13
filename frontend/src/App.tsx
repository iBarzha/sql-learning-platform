import { lazy, Suspense, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { QueryClientProvider } from '@tanstack/react-query';
import { queryClient } from '@/lib/queryClient';
import { useAuthStore } from '@/store/authStore';
import { usePreferencesStore } from '@/store/preferencesStore';
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { MainLayout } from '@/components/layout';
import { Spinner } from '@/components/ui/spinner';
import { ErrorBoundary } from '@/components/ErrorBoundary';

// Lazy-loaded page components
const LoginPage = lazy(() => import('@/pages/auth/LoginPage').then(m => ({ default: m.LoginPage })));
const ChangePasswordPage = lazy(() => import('@/pages/auth/ChangePasswordPage').then(m => ({ default: m.ChangePasswordPage })));
const DashboardPage = lazy(() => import('@/pages/dashboard/DashboardPage').then(m => ({ default: m.DashboardPage })));
const CoursesListPage = lazy(() => import('@/pages/courses/CoursesListPage').then(m => ({ default: m.CoursesListPage })));
const CourseDetailPage = lazy(() => import('@/pages/courses/CourseDetailPage').then(m => ({ default: m.CourseDetailPage })));
const LessonPage = lazy(() => import('@/pages/lessons/LessonPage').then(m => ({ default: m.LessonPage })));
const AssignmentPage = lazy(() => import('@/pages/assignments/AssignmentPage').then(m => ({ default: m.AssignmentPage })));
const ProfilePage = lazy(() => import('@/pages/profile/ProfilePage').then(m => ({ default: m.ProfilePage })));
const SandboxPage = lazy(() => import('@/pages/sandbox/SandboxPage').then(m => ({ default: m.SandboxPage })));
const MyCoursesPage = lazy(() => import('@/pages/instructor/MyCoursesPage').then(m => ({ default: m.MyCoursesPage })));
const CourseFormPage = lazy(() => import('@/pages/instructor/CourseFormPage').then(m => ({ default: m.CourseFormPage })));
const CourseManagePage = lazy(() => import('@/pages/instructor/CourseManagePage').then(m => ({ default: m.CourseManagePage })));
const LessonFormPage = lazy(() => import('@/pages/instructor/LessonFormPage').then(m => ({ default: m.LessonFormPage })));
const StudentsPage = lazy(() => import('@/pages/instructor/StudentsPage').then(m => ({ default: m.StudentsPage })));
const AllStudentsPage = lazy(() => import('@/pages/instructor/AllStudentsPage').then(m => ({ default: m.AllStudentsPage })));
const SettingsPage = lazy(() => import('@/pages/admin/SettingsPage').then(m => ({ default: m.SettingsPage })));
const UserManagementPage = lazy(() => import('@/pages/admin/UserManagementPage').then(m => ({ default: m.UserManagementPage })));

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
    <Suspense fallback={<div className="min-h-screen flex items-center justify-center"><Spinner size="lg" /></div>}>
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
    </Suspense>
  );
}

function App() {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <AppRoutes />
        </BrowserRouter>
      </QueryClientProvider>
    </ErrorBoundary>
  );
}

export default App;
