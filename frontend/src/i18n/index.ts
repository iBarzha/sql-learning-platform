import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import LanguageDetector from 'i18next-browser-languagedetector';

// English translations
import enCommon from '@/i18n/locales/en/common.json';
import enAuth from '@/i18n/locales/en/auth.json';
import enDashboard from '@/i18n/locales/en/dashboard.json';
import enCourses from '@/i18n/locales/en/courses.json';
import enLessons from '@/i18n/locales/en/lessons.json';
import enSandbox from '@/i18n/locales/en/sandbox.json';
import enInstructor from '@/i18n/locales/en/instructor.json';
import enAdmin from '@/i18n/locales/en/admin.json';
import enProfile from '@/i18n/locales/en/profile.json';
import enEditor from '@/i18n/locales/en/editor.json';

// Ukrainian translations
import ukCommon from '@/i18n/locales/uk/common.json';
import ukAuth from '@/i18n/locales/uk/auth.json';
import ukDashboard from '@/i18n/locales/uk/dashboard.json';
import ukCourses from '@/i18n/locales/uk/courses.json';
import ukLessons from '@/i18n/locales/uk/lessons.json';
import ukSandbox from '@/i18n/locales/uk/sandbox.json';
import ukInstructor from '@/i18n/locales/uk/instructor.json';
import ukAdmin from '@/i18n/locales/uk/admin.json';
import ukProfile from '@/i18n/locales/uk/profile.json';
import ukEditor from '@/i18n/locales/uk/editor.json';

export const defaultNS = 'common';

export const resources = {
  en: {
    common: enCommon,
    auth: enAuth,
    dashboard: enDashboard,
    courses: enCourses,
    lessons: enLessons,
    sandbox: enSandbox,
    instructor: enInstructor,
    admin: enAdmin,
    profile: enProfile,
    editor: enEditor,
  },
  uk: {
    common: ukCommon,
    auth: ukAuth,
    dashboard: ukDashboard,
    courses: ukCourses,
    lessons: ukLessons,
    sandbox: ukSandbox,
    instructor: ukInstructor,
    admin: ukAdmin,
    profile: ukProfile,
    editor: ukEditor,
  },
} as const;

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources,
    defaultNS,
    ns: [
      'common',
      'auth',
      'dashboard',
      'courses',
      'lessons',
      'sandbox',
      'instructor',
      'admin',
      'profile',
      'editor',
    ],
    fallbackLng: 'en',
    interpolation: {
      escapeValue: false,
    },
    detection: {
      order: ['localStorage', 'navigator'],
      lookupLocalStorage: 'i18nextLng',
      caches: ['localStorage'],
    },
  });

export default i18n;
