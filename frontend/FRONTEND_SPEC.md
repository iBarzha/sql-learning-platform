# SQL Learning Platform -- Frontend Specification

> **Generated**: 2026-02-10
> **Codebase Path**: `sql-learning-platform/frontend/src/`
> **Framework**: React 19.2 + TypeScript 5.9 + Vite 7.2

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Theme System](#2-theme-system)
3. [i18n System](#3-i18n-system)
4. [UI Component Library](#4-ui-component-library)
5. [Layout System](#5-layout-system)
6. [Routing](#6-routing)
7. [State Management](#7-state-management)
8. [Pages](#8-pages)
9. [Monaco Editor](#9-monaco-editor)
10. [Charts](#10-charts)
11. [Forms](#11-forms)
12. [API Layer](#12-api-layer)
13. [Design Tokens](#13-design-tokens)
14. [Responsive Design](#14-responsive-design)

---

## 1. Architecture Overview

### 1.1 Technology Stack

| Layer | Technology | Version |
|---|---|---|
| UI Framework | React | 19.2.0 |
| Language | TypeScript | ~5.9.3 |
| Build Tool | Vite | 7.2.4 |
| Styling | Tailwind CSS (v4) | 4.1.18 |
| Routing | react-router-dom | 7.13.0 |
| State (client) | Zustand | 5.0.11 |
| State (server) | TanStack React Query | 5.90.20 |
| Forms | react-hook-form + zod | 7.71.1 / 4.3.6 |
| HTTP | Axios | 1.13.4 |
| i18n | i18next + react-i18next | 25.8.4 / 16.5.4 |
| Code Editor | @monaco-editor/react | 4.7.0 |
| Charts | Recharts | 3.7.0 |
| Toasts | Sonner | 2.0.7 |
| Icons | lucide-react | 0.563.0 |
| UI Primitives | Radix UI | Multiple packages |
| Markdown | react-markdown | 10.1.0 |
| Client SQLite | sql.js (WASM) | 1.13.0 |
| CSS Utilities | class-variance-authority, clsx, tailwind-merge | 0.7.1 / 2.1.1 / 3.4.0 |

### 1.2 Project Structure

```
src/
  main.tsx                     # Entry point: StrictMode, CSS, i18n init, App mount
  App.tsx                      # BrowserRouter, QueryClientProvider, route definitions
  index.css                    # Tailwind import, CSS custom properties, theme system
  i18n/
    index.ts                   # i18next configuration, namespace imports
    locales/
      en/                      # 10 English JSON namespace files
      uk/                      # 10 Ukrainian JSON namespace files
  store/
    authStore.ts               # Zustand auth store (user, tokens, login/register/logout)
    preferencesStore.ts        # Zustand preferences store (theme, locale)
  api/
    client.ts                  # Axios instance, interceptors, JWT refresh
    auth.ts                    # Auth endpoints
    courses.ts                 # Course CRUD + enrollments + datasets
    lessons.ts                 # Lesson CRUD + submissions
    modules.ts                 # Module CRUD + reorder
    assignments.ts             # Assignment CRUD + reorder
    submissions.ts             # Submission endpoints + progress
    sandbox.ts                 # Sandbox execution + DB types + datasets
    attachments.ts             # File upload/download for lessons
  hooks/
    useSqlite.ts               # Client-side SQLite DB lifecycle via sql.js WASM
    queries/
      useCourses.ts            # React Query hooks for courses
      useLessons.ts            # React Query hooks for lessons
      useModules.ts            # React Query hooks for modules
      useAssignments.ts        # React Query hooks for assignments
      useSubmissions.ts        # React Query hooks for submissions + progress
      useSandbox.ts            # React Query hooks for sandbox DB types/datasets
      useAttachments.ts        # React Query hooks for file attachments
  lib/
    utils.ts                   # cn() helper, getApiErrorMessage()
    schemas.ts                 # Zod validation schemas
    queryClient.ts             # TanStack Query client configuration
    sqljs.ts                   # sql.js WASM loader + query executor
  types/
    index.ts                   # All TypeScript interfaces (User, Course, Assignment, etc.)
    sql.js.d.ts                # Type declarations for sql.js module
  components/
    auth/
      ProtectedRoute.tsx       # Auth guard, role check, must_change_password redirect
    ui/                        # 20 reusable UI primitives
    layout/                    # MainLayout, Sidebar, Header, ThemeToggle, etc.
    editor/                    # SqlEditor, monacoThemes, SqlExerciseBlock
    charts/                    # StatCard, ProgressRing, MiniChart
  pages/
    auth/                      # LoginPage, RegisterPage, ChangePasswordPage
    dashboard/                 # DashboardPage
    courses/                   # CoursesListPage, CourseDetailPage
    lessons/                   # LessonPage
    assignments/               # AssignmentPage
    sandbox/                   # SandboxPage
    profile/                   # ProfilePage
    instructor/                # MyCoursesPage, CourseFormPage, CourseManagePage,
                               #   LessonFormPage, StudentsPage, AllStudentsPage
    admin/                     # SettingsPage
```

### 1.3 Build Configuration

**Vite Config** (`vite.config.ts`):
- Plugins: `@vitejs/plugin-react`, `@tailwindcss/vite`
- Path alias: `@/` resolves to `./src/`
- `optimizeDeps.include`: `['sql.js']` -- pre-bundles the WASM module
- Dev server port: `5173`
- API proxy: `/api` proxied to `http://localhost:8000`

**TypeScript Config** (`tsconfig.app.json`):
- Target: ES2022
- Strict mode enabled
- `noUnusedLocals`, `noUnusedParameters` enabled
- Path alias: `@/*` maps to `./src/*`
- JSX: react-jsx

**Docker** (`Dockerfile.dev`):
- Base: `node:20-alpine`
- Exposes port 5173
- CMD: `npm run dev -- --host`

### 1.4 Entry Point Flow

1. `index.html` executes an **anti-flash inline script** (reads `preferences-storage` from localStorage, applies `.dark` class before first paint)
2. `main.tsx` imports `index.css` (Tailwind + theme), `i18n` (side-effect init), `preferencesStore` (side-effect: applies theme class)
3. `App` renders `QueryClientProvider` > `BrowserRouter` > `AppRoutes`
4. `AppRoutes` calls `fetchUser()` on mount, shows `Spinner` while loading, then renders route tree

---

## 2. Theme System

### 2.1 Theme Modes

Three modes: `system`, `light`, `dark`. Stored in Zustand `preferencesStore` and persisted to `localStorage` under key `preferences-storage`.

**Resolution logic** (`preferencesStore.ts`):
- `system` resolves via `window.matchMedia('(prefers-color-scheme: dark)')`
- A `change` event listener on the media query auto-updates when system preference changes
- `applyThemeClass()` adds/removes `.dark` on `document.documentElement`

### 2.2 Anti-Flash Script

Inline `<script>` in `index.html` runs before any module loads:
```js
var prefs = JSON.parse(localStorage.getItem('preferences-storage') || '{}');
var theme = prefs.state?.theme || 'system';
var dark = theme === 'dark' || (theme === 'system' && matchMedia('(prefers-color-scheme: dark)').matches);
if (dark) document.documentElement.classList.add('dark');
```
This prevents the white flash on dark-mode page loads.

### 2.3 NobleFinance HSL Palette

All colors are defined as HSL triplets (without `hsl()` wrapper) as CSS custom properties in `:root` and `.dark`:

**Light Theme** (`:root`):

| Token | HSL Value |
|---|---|
| `--background` | `70 15% 96%` |
| `--foreground` | `70 10% 12%` |
| `--card` | `0 0% 100%` |
| `--card-foreground` | `70 10% 12%` |
| `--popover` | `0 0% 100%` |
| `--popover-foreground` | `70 10% 12%` |
| `--primary` | `90 25% 49%` |
| `--primary-foreground` | `0 0% 100%` |
| `--secondary` | `80 15% 92%` |
| `--secondary-foreground` | `70 10% 20%` |
| `--muted` | `80 10% 93%` |
| `--muted-foreground` | `0 1% 54%` |
| `--accent` | `80 18% 82%` |
| `--accent-foreground` | `70 10% 15%` |
| `--destructive` | `5 60% 52%` |
| `--destructive-foreground` | `0 0% 100%` |
| `--success` | `90 25% 49%` |
| `--success-foreground` | `0 0% 100%` |
| `--warning` | `40 80% 55%` |
| `--warning-foreground` | `0 0% 100%` |
| `--border` | `70 12% 88%` |
| `--input` | `70 12% 88%` |
| `--ring` | `90 25% 49%` |
| `--radius` | `0.75rem` |
| `--chart-1` through `--chart-5` | See Section 13 |
| `--shadow-color` | `70 10% 40%` |
| `--glass-bg` | `0 0% 100% / 0.7` |
| `--glass-border` | `0 0% 100% / 0.3` |

**Dark Theme** (`.dark`):

| Token | HSL Value |
|---|---|
| `--background` | `70 8% 11%` |
| `--foreground` | `80 15% 85%` |
| `--card` | `70 8% 14%` |
| `--card-foreground` | `80 15% 85%` |
| `--popover` | `70 8% 14%` |
| `--popover-foreground` | `80 15% 85%` |
| `--primary` | `90 25% 49%` |
| `--primary-foreground` | `0 0% 100%` |
| `--secondary` | `70 8% 18%` |
| `--secondary-foreground` | `80 15% 80%` |
| `--muted` | `70 6% 18%` |
| `--muted-foreground` | `0 1% 54%` |
| `--accent` | `80 18% 30%` |
| `--accent-foreground` | `80 15% 85%` |
| `--destructive` | `5 60% 45%` |
| `--destructive-foreground` | `80 15% 95%` |
| `--success` | `90 30% 45%` |
| `--success-foreground` | `0 0% 100%` |
| `--warning` | `40 80% 50%` |
| `--warning-foreground` | `0 0% 100%` |
| `--border` | `70 6% 22%` |
| `--input` | `70 6% 22%` |
| `--ring` | `90 25% 49%` |
| `--shadow-color` | `0 0% 0%` |
| `--glass-bg` | `70 8% 14% / 0.7` |
| `--glass-border` | `80 15% 85% / 0.08` |

### 2.4 Glass-Morphism Utilities

```css
.glass {
  background: hsl(var(--glass-bg));
  backdrop-filter: blur(12px);
  border: 1px solid hsl(var(--glass-border));
}
.glass-heavy {
  background: hsl(var(--glass-bg));
  backdrop-filter: blur(20px);
  border: 1px solid hsl(var(--glass-border));
}
```

### 2.5 Shadow Utilities

```css
.shadow-noble-sm   /* 0 1px 2px, 0 1px 3px */
.shadow-noble      /* 0 2px 4px, 0 4px 12px */
.shadow-noble-md   /* 0 4px 6px, 0 6px 16px */
.shadow-noble-lg   /* 0 10px 15px, 0 12px 24px */
```

All shadow utilities use `hsl(var(--shadow-color))` with varying alpha so they adapt between light and dark themes.

### 2.6 Animation Utilities

```css
.animate-fade-in   /* 0.3s ease-out, opacity 0 -> 1 */
.animate-slide-up  /* 0.3s ease-out, translateY(8px) + opacity 0 -> 0 + 1 */
.animate-scale-in  /* 0.2s ease-out, scale(0.95) + opacity 0 -> 1 + 1 */
```

### 2.7 Tailwind v4 Theme Mapping

The `@theme inline` block at the bottom of `index.css` maps CSS custom properties to Tailwind color tokens:

```
--color-primary    -> hsl(var(--primary))
--color-background -> hsl(var(--background))
--radius-sm        -> calc(var(--radius) - 4px)
--radius-md        -> calc(var(--radius) - 2px)
--radius-lg        -> var(--radius)
--radius-xl        -> calc(var(--radius) + 4px)
--radius-2xl       -> calc(var(--radius) + 8px)
```

This enables usage like `bg-primary`, `text-foreground`, `rounded-lg` etc.

### 2.8 Scrollbar Styling

Custom WebKit scrollbar: 6px width, transparent track, `muted-foreground` thumb at 25% opacity (40% on hover), 3px border-radius.

### 2.9 Selection Styling

Selected text uses `primary/0.25` background with `foreground` text color.

---

## 3. i18n System

### 3.1 Setup

**File**: `src/i18n/index.ts`

- Library: `i18next` + `react-i18next` + `i18next-browser-languagedetector`
- Default language: `en`
- Fallback language: `en`
- Detection order: `['localStorage', 'navigator']`
- Cache: `['localStorage']`
- Escape: disabled (`escapeValue: false`)
- All translations bundled statically (no lazy loading)

### 3.2 Namespaces (10 total)

| Namespace | Description |
|---|---|
| `common` | Navigation, actions, statuses, theme labels, misc |
| `auth` | Login, register, change password, branding, validation |
| `dashboard` | Welcome messages, stat labels, course progress |
| `courses` | Course list, course detail, enrollment, lesson types |
| `lessons` | Lesson page, query UI, hints, results, attachments |
| `sandbox` | SQL sandbox, DB types, datasets, results, quick start |
| `instructor` | My courses, course form, manage, lesson form, students |
| `admin` | Settings, system status, DB info, quick actions |
| `profile` | Personal info, security, update success |
| `editor` | SQL exercise block labels (try it yourself, hint, run, reset) |

### 3.3 Locales

- **EN** (English) -- Complete
- **UK** (Ukrainian) -- Complete

### 3.4 Complete Translation Key Reference

#### `common` namespace
```
navigation.dashboard, navigation.courses, navigation.sandbox,
navigation.myCourses, navigation.students, navigation.settings,
navigation.profile, navigation.changePassword, navigation.logout

actions.save, actions.cancel, actions.delete, actions.edit,
actions.create, actions.search, actions.back, actions.submit,
actions.run, actions.reset, actions.show, actions.hide,
actions.loading, actions.viewAll

status.online, status.offline, status.active, status.inactive,
status.draft, status.published, status.completed, status.pending,
status.error, status.success

theme.light, theme.dark, theme.system

language.english, language.ukrainian

misc.noResults, misc.noData, misc.confirmDelete, misc.pageNotFound
```

**Note**: The Sidebar component uses `common:nav.dashboard`, `common:nav.courses`, `common:nav.sandbox`, `common:nav.myCourses`, `common:nav.students`, `common:nav.settings`, `common:nav.profile`, `common:nav.changePassword`, `common:nav.logout`. The actual JSON uses `navigation.*` keys. The `t()` calls in code reference `common:nav.*` which maps to the `navigation` sub-object via i18next's key separator. The ThemeToggle uses `common:theme.system`, `common:theme.light`, `common:theme.dark`. The LanguageSwitcher uses `common:language.switch`.

#### `auth` namespace
```
branding.name, branding.tagline, branding.startJourney

decorative.comment, decorative.commentRegister, decorative.tagline

fields.email, fields.emailPlaceholder, fields.password,
fields.firstName, fields.firstNamePlaceholder,
fields.lastName, fields.lastNamePlaceholder,
fields.confirmPassword

login.title, login.subtitle, login.submit,
login.noAccount, login.signUpLink

register.title, register.subtitle, register.submit,
register.hasAccount, register.signInLink,
register.passwordStrength.weak, register.passwordStrength.fair,
register.passwordStrength.strong

changePassword.title, changePassword.setTitle,
changePassword.subtitle, changePassword.setSubtitle,
changePassword.currentPassword, changePassword.newPassword,
changePassword.confirmNewPassword, changePassword.submit,
changePassword.setSubmit, changePassword.error

validation.emailRequired, validation.emailInvalid,
validation.passwordRequired, validation.passwordMin,
validation.passwordsNoMatch, validation.confirmRequired
```

#### `dashboard` namespace
```
welcome.title (interpolates {{name}})
welcome.instructorSubtitle, welcome.studentSubtitle

stats.enrolledCourses, stats.completed,
stats.ofLessons (interpolates {{count}}),
stats.inProgress, stats.avgScore

courses.title, courses.subtitle,
courses.noCourses, courses.noCoursesDesc,
courses.browseCourses, courses.by (interpolates {{name}})
```

#### `courses` namespace
```
list.title, list.subtitle, list.createCourse,
list.searchPlaceholder, list.noCourses, list.noCoursesSearch,
list.noCoursesAvailable, list.lessons (interpolates {{count}})

detail.aboutCourse, detail.lessons,
detail.lessonsCount (interpolates {{count}}),
detail.courseInfo, detail.students, detail.database,
detail.startDate, detail.endDate, detail.enroll,
detail.enrollNow, detail.enrollmentKey,
detail.unenroll, detail.yourProgress, detail.progress,
detail.practiceCompleted (interpolates {{completed}}, {{total}}),
detail.courseNotFound, detail.backToCourses,
detail.enrollInCourse

types.theory, types.practice, types.mixed
enrolled, otherLessons
```

#### `lessons` namespace
```
page.task, page.yourQuery, page.pressCtrlEnter,
page.runQuery, page.attemptsLeft ({{count}}),
page.timeLimit ({{seconds}}), page.queryOutput,
page.result, page.correct, page.incorrect,
page.score ({{score}}, {{max}}),
page.executionTime ({{time}}),
page.showingRows ({{shown}}, {{total}}),
page.databaseSchema, page.hints,
page.hint ({{current}}, {{total}}),
page.lessonNotFound, page.backToCourse,
page.completed, page.noTheory, page.completeTask

attachments.title ({{count}})
```

#### `sandbox` namespace
```
title, subtitle, database, dataset,
customSchema, schema, createStatements,
seedData, query, queryDescription,
results, success, sessionActive, resetSession,
quickStart, tryExamples, basicSelect, groupBy, join,
noRows, rowsAffected ({{count}}),
showingRows ({{shown}}, {{total}}),
clear, datasetDescription, hide, show,
runQuery, error
```

#### `instructor` namespace
```
myCourses.title, myCourses.subtitle, myCourses.newCourse,
myCourses.noCourses, myCourses.noCoursesDesc,
myCourses.createCourse, myCourses.published, myCourses.draft,
myCourses.manage, myCourses.duplicate, myCourses.view,
myCourses.lessons ({{count}})

courseForm.createTitle, courseForm.editTitle,
courseForm.createSubtitle, courseForm.editSubtitle,
courseForm.courseDetails, courseForm.courseDetailsDesc,
courseForm.title, courseForm.description,
courseForm.databaseType, courseForm.startDate, courseForm.endDate,
courseForm.enrollmentSettings, courseForm.enrollmentSettingsDesc,
courseForm.enrollmentKey, courseForm.enrollmentKeyDesc,
courseForm.maxStudents, courseForm.saveCourse,
courseForm.createCourse, courseForm.cancel

courseManage.title, courseManage.manageContent,
courseManage.modules, courseManage.modulesCount ({{count}}),
courseManage.addModule, courseManage.moduleTitlePlaceholder,
courseManage.lessons, courseManage.lessonsCount ({{count}}),
courseManage.addLesson, courseManage.addFirstLesson,
courseManage.noLessons, courseManage.noLessonsDesc,
courseManage.publish, courseManage.unpublish,
courseManage.settings, courseManage.studentsCount ({{count}}),
courseManage.duplicate, courseManage.published, courseManage.draft,
courseManage.courseNotFound, courseManage.backToMyCourses,
courseManage.add, courseManage.deleteLesson,
courseManage.deleteLessonConfirm, courseManage.deleteModule,
courseManage.deleteModuleConfirm, courseManage.confirm,
courseManage.cancel, courseManage.theory,
courseManage.practice, courseManage.mixed

lessonForm.createTitle, lessonForm.editTitle,
lessonForm.createSubtitle, lessonForm.editSubtitle,
lessonForm.basicInfo, lessonForm.titleLabel,
lessonForm.descriptionLabel, lessonForm.lessonType,
lessonForm.module, lessonForm.noModule,
lessonForm.theoryContent, lessonForm.theoryContentDesc,
lessonForm.markdown, lessonForm.practiceTask,
lessonForm.practiceTaskDesc, lessonForm.datasetLabel,
lessonForm.noDataset, lessonForm.taskDescription,
lessonForm.initialCode, lessonForm.expectedQuery,
lessonForm.maxScore, lessonForm.timeLimit,
lessonForm.maxAttempts, lessonForm.unlimited,
lessonForm.hints, lessonForm.hintsDesc,
lessonForm.addHint, lessonForm.hintPlaceholder,
lessonForm.attachments, lessonForm.attachmentsDesc,
lessonForm.publishImmediately, lessonForm.saveChanges,
lessonForm.createLesson, lessonForm.cancel

students.title, students.courseStudents ({{title}}),
students.enrolledStudents,
students.studentsEnrolled ({{count}}),
students.searchPlaceholder, students.noStudents,
students.noStudentsYet, students.noStudentsSearch,
students.adjustSearch, students.grade,
students.allStudentsTitle, students.allStudentsSubtitle,
students.allStudents,
students.studentsAcrossCourses ({{studentCount}}, {{courseCount}}),
students.noStudentsEnrolled,
students.courseCount ({{count}}), students.courseCount_plural,
students.courseNotFound, students.backToMyCourses
```

#### `admin` namespace
```
settings.title, settings.subtitle

status.title, status.apiServer, status.database,
status.sandboxPool, status.available ({{count}})

dbInfo.title, dbInfo.type, dbInfo.host, dbInfo.databaseName

quickActions.title, quickActions.djangoAdmin, quickActions.apiBrowser

config.title, config.subtitle, config.description
```

#### `profile` namespace
```
title, subtitle

personalInfo.title, personalInfo.subtitle,
personalInfo.fullName, personalInfo.firstName,
personalInfo.lastName, personalInfo.email,
personalInfo.role, personalInfo.memberSince,
personalInfo.edit, personalInfo.save, personalInfo.cancel

security.title, security.subtitle, security.changePassword

updateSuccess
```

#### `editor` namespace
```
tryItYourself, hint, reset, run, loading,
writeQuery, rowsAffected ({{count}}), executionTime ({{time}})
```

---

## 4. UI Component Library

All components live in `src/components/ui/`. They use `class-variance-authority` (CVA) for variant management, `@radix-ui` primitives for accessible behaviors, and the `cn()` utility for class merging.

### 4.1 Button

**File**: `button.tsx`

**Variants**:
| Variant | Styles |
|---|---|
| `default` | Primary bg, white text, noble shadow, hover shadow-md |
| `destructive` | Destructive bg, white text, hover at 90% |
| `outline` | Border, bg-background, hover bg-secondary |
| `secondary` | Secondary bg, secondary text, hover at 80% |
| `ghost` | Transparent, hover bg-secondary |
| `link` | Primary text, underline on hover |
| `success` | Success bg, white text, noble shadow |

**Sizes**:
| Size | Dimensions |
|---|---|
| `default` | h-10, px-5 py-2 |
| `xs` | h-7, rounded-lg, px-2.5, text-xs |
| `sm` | h-9, rounded-lg, px-4 |
| `lg` | h-12, rounded-xl, px-8 |
| `icon` | h-10 w-10 |

**Props**: `variant`, `size`, `asChild` (renders via Radix `Slot`), plus all native `<button>` attributes.

**Features**: `active:scale-[0.98]` press effect, 200ms transition, ring-based focus styles.

### 4.2 Input

**File**: `input.tsx`

Standard input with: h-10, rounded-xl, border-border/60, focus ring primary/30, border-primary/50 on focus. 200ms transitions. Responsive text: `text-base` mobile, `md:text-sm`.

### 4.3 Textarea

**File**: `textarea.tsx`

Min-height 80px, `resize-none`, rounded-xl. Same focus styles as Input.

### 4.4 Card

**File**: `card.tsx`

**Variants**:
| Variant | Styles |
|---|---|
| `default` | border-border/50, bg-card, shadow-noble, hover shadow-noble-md |
| `glass` | Uses `.glass` utility, rounded-2xl, shadow-noble |

**Sub-components**: `CardHeader` (p-6), `CardTitle` (text-xl font-semibold), `CardDescription` (text-sm text-muted-foreground), `CardContent` (p-6 pt-0), `CardFooter` (flex p-6 pt-0).

### 4.5 Badge

**File**: `badge.tsx`

**Variants**:
| Variant | Styles |
|---|---|
| `default` | Primary bg, white text |
| `secondary` | Secondary bg, secondary text |
| `destructive` | Destructive/10 bg, destructive text |
| `outline` | Border-border/60, muted text |
| `success` | Success/10 bg, success text |
| `warning` | Warning/10 bg, warning text |

Rounded-lg, px-2.5 py-0.5, text-xs font-medium.

### 4.6 Label

**File**: `label.tsx`

Text-sm, font-medium, peer-disabled opacity. CVA-based but no explicit variants beyond the base style.

### 4.7 Spinner

**File**: `spinner.tsx`

SVG-based spinner. **Sizes**: `sm` (h-4 w-4), `md` (h-6 w-6), `lg` (h-8 w-8). Uses `animate-spin` and `text-primary`.

### 4.8 Alert

**File**: `alert.tsx`

**Variants**:
| Variant | Styles |
|---|---|
| `default` | bg-background, text-foreground |
| `destructive` | border-destructive/50, text-destructive |
| `success` | border-success/50, text-success, bg-success/5 |
| `warning` | border-warning/50, text-warning, bg-warning/5 |

**Sub-components**: `AlertTitle`, `AlertDescription`. Rounded-xl, supports SVG icon positioning.

### 4.9 Avatar

**File**: `avatar.tsx`

**Sizes**: `sm` (h-8 w-8), `default` (h-10 w-10), `lg` (h-12 w-12). Rounded-full, overflow-hidden.

**Sub-components**: `AvatarImage`, `AvatarFallback` (bg-primary/10, text-primary, font-semibold, size-aware text scaling).

### 4.10 Skeleton

**File**: `skeleton.tsx`

`animate-pulse`, `rounded-xl`, `bg-muted`. Takes `className` for dimension customization.

### 4.11 Progress

**File**: `progress.tsx`

Background track: h-2, bg-secondary, rounded-full. Foreground indicator animated with 500ms ease-out width transition.

**Indicator Variants**: `default` (bg-primary), `success`, `warning`, `destructive`.

**Props**: `value` (0-100, clamped), `variant`.

### 4.12 Table

**File**: `table.tsx`

Composable table primitives: `Table`, `TableHeader`, `TableBody`, `TableFooter`, `TableRow`, `TableHead`, `TableCell`, `TableCaption`. Wrapped in `overflow-auto`. Hover rows at `bg-muted/30`. Head cells use `text-xs font-medium uppercase text-muted-foreground`. Body cells use `font-mono text-xs`.

### 4.13 Select

**File**: `select.tsx`

Built on `@radix-ui/react-select`. Styled trigger with rounded-xl, chevron icon, focus ring. Content uses `animate-scale-in`, shadow-noble-lg. Items are rounded-lg with focus highlight.

**Exports**: `Select`, `SelectGroup`, `SelectValue`, `SelectTrigger`, `SelectContent`, `SelectLabel`, `SelectItem`, `SelectSeparator`, `SelectScrollUpButton`, `SelectScrollDownButton`.

### 4.14 Dialog

**File**: `dialog.tsx`

Built on `@radix-ui/react-dialog`. Overlay uses `backdrop-blur-sm`, `bg-foreground/20`. Content is centered, rounded-2xl, uses `.glass` utility, `animate-scale-in`. Close button is `X` icon in top-right.

**Exports**: `Dialog`, `DialogPortal`, `DialogOverlay`, `DialogClose`, `DialogTrigger`, `DialogContent`, `DialogHeader`, `DialogFooter`, `DialogTitle`, `DialogDescription`.

### 4.15 Tabs

**File**: `tabs.tsx`

Built on `@radix-ui/react-tabs`. Tab list uses `.glass` with p-1. Active trigger: `bg-card`, `shadow-noble-sm`. Content animates with `animate-fade-in`.

**Exports**: `Tabs`, `TabsList`, `TabsTrigger`, `TabsContent`.

### 4.16 Tooltip

**File**: `tooltip.tsx`

Built on `@radix-ui/react-tooltip`. Content: `bg-foreground`, `text-background`, rounded-lg, shadow-noble-md, `animate-scale-in`.

**Exports**: `TooltipProvider`, `Tooltip`, `TooltipTrigger`, `TooltipContent`.

### 4.17 DropdownMenu

**File**: `dropdown-menu.tsx`

Built on `@radix-ui/react-dropdown-menu`. Content: min-w-180px, rounded-xl, border-border/50, shadow-noble-lg, `animate-scale-in`. Items: rounded-lg, cursor-pointer, 150ms transition.

**Exports**: `DropdownMenu`, `DropdownMenuTrigger`, `DropdownMenuContent`, `DropdownMenuItem`, `DropdownMenuLabel`, `DropdownMenuSeparator`, `DropdownMenuShortcut`, `DropdownMenuGroup`, `DropdownMenuPortal`, `DropdownMenuSub`, `DropdownMenuRadioGroup`.

### 4.18 Switch

**File**: `switch.tsx`

Built on `@radix-ui/react-switch`. h-6 w-11, rounded-full. Checked: `bg-primary`. Thumb: h-5 w-5, rounded-full, `shadow-noble-sm`, 200ms translate animation.

### 4.19 Separator

**File**: `separator.tsx`

Built on `@radix-ui/react-separator`. `bg-border/50`. Horizontal: h-px w-full. Vertical: h-full w-px.

### 4.20 Toaster (Sonner)

**File**: `sonner.tsx`

Wraps `sonner`'s `Toaster`. Reads `resolvedTheme` from preferencesStore. Toasts use: rounded-xl, shadow-noble-lg, border-border/50, bg-card, text-foreground. Rich colors enabled.

### 4.21 FileUpload

**File**: `FileUpload.tsx`

Drag-and-drop + click file upload. Props: `onUpload(file)`, `isUploading`, `maxSizeMB` (default 10), `accept`. Features: drag highlight, file size validation, error display. Dashed border, rounded-xl. Also exports `formatFileSize()` and `getFileTypeIcon()` helpers.

---

## 5. Layout System

### 5.1 MainLayout

**File**: `components/layout/MainLayout.tsx`

Structure:
```
<div min-h-screen bg-background>
  <Header onMenuClick />
  <Sidebar isOpen onClose />
  <main md:pl-16>
    <div px-6 py-8 md:px-10 md:py-10 max-w-7xl mx-auto>
      <Outlet />
    </div>
  </main>
  <Toaster />
</div>
```

The `main` content is offset by `md:pl-16` (4rem = 64px) to accommodate the collapsed sidebar width on desktop.

### 5.2 Header

**File**: `components/layout/Header.tsx`

- Sticky (`sticky top-0 z-50`), h-14, `glass-heavy`, `shadow-noble-sm`
- Left: Mobile hamburger button (hidden on md+), Logo link (Database icon + "SQL Learning" text, text hidden on mobile)
- Right: `ThemeToggle`, `LanguageSwitcher`, `UserMenu` (wrapped in `TooltipProvider`)

### 5.3 Sidebar

**File**: `components/layout/Sidebar.tsx`

**Desktop** (hidden on mobile):
- Fixed left, top-14, z-30, h-[calc(100vh-3.5rem)]
- Width: `w-16` (collapsed, icon-only) expanding to `w-56` on hover via `hover:w-56 transition-all duration-300`
- Uses `glass-heavy`, `shadow-noble-sm`
- CSS group `group/sidebar` enables child elements to respond to hover
- Nav items: icon (w-12 centered) + label (opacity-0, fades in on hover with 75ms delay)
- Tooltips on icons appear only when sidebar is collapsed (`group-hover/sidebar:hidden`)
- Active item: `bg-primary text-primary-foreground shadow-noble-sm`
- Bottom: branded section with Database icon and "SQL Learning" text

**Mobile** (hidden on desktop):
- Triggered by hamburger button in Header
- Full-height overlay sidebar (`w-72`), slides in from left (`translate-x-0` / `-translate-x-full`)
- Backdrop: `bg-foreground/20 backdrop-blur-sm`
- Close button in sidebar header
- Includes user info section at bottom

**Navigation Items** (role-filtered):
| Path | Icon | i18n Key | Roles |
|---|---|---|---|
| `/` | LayoutDashboard | `common:nav.dashboard` | All |
| `/courses` | BookOpen | `common:nav.courses` | All |
| `/sandbox` | Database | `common:nav.sandbox` | All |
| `/my-courses` | GraduationCap | `common:nav.myCourses` | instructor, admin |
| `/students` | Users | `common:nav.students` | instructor, admin |
| `/settings` | Settings | `common:nav.settings` | admin |

### 5.4 ThemeToggle

**File**: `components/layout/ThemeToggle.tsx`

Cycles through `system` -> `light` -> `dark` on each click. Icons: Monitor, Sun, Moon. Ghost button, icon size, rounded-xl. Tooltip shows current mode name.

### 5.5 LanguageSwitcher

**File**: `components/layout/LanguageSwitcher.tsx`

Toggles between `en` and `uk`. Displays current locale code ("EN" or "UK") as button text. Updates both `preferencesStore.locale` and `i18n.changeLanguage()`. Ghost button, sm size, font-semibold, w-10.

### 5.6 UserMenu

**File**: `components/layout/UserMenu.tsx`

Dropdown menu triggered by avatar button (rounded-full). Shows user initials. Menu content (w-56, right-aligned):
- Label: full name + email
- Separator
- Profile link (User icon)
- Change Password link (Key icon)
- Separator
- Logout (LogOut icon, destructive styling)

---

## 6. Routing

### 6.1 Route Tree

```
/login                                    # Public  -- LoginPage
/register                                 # Public  -- RegisterPage
/                                         # Protected (MainLayout wrapper)
  (index)                                 # DashboardPage
  /courses                                # CoursesListPage
  /courses/:courseId                       # CourseDetailPage
  /courses/:courseId/lessons/:lessonId     # LessonPage
  /courses/:courseId/assignments/:assignmentId  # AssignmentPage
  /sandbox                                # SandboxPage
  /profile                                # ProfilePage
  /change-password                        # ChangePasswordPage
  /my-courses                             # MyCoursesPage       (instructor/admin)
  /courses/new                            # CourseFormPage       (instructor/admin)
  /courses/:courseId/edit                  # CourseFormPage       (instructor/admin)
  /courses/:courseId/manage               # CourseManagePage     (instructor/admin)
  /courses/:courseId/lessons/new           # LessonFormPage       (instructor/admin)
  /courses/:courseId/lessons/:lessonId/edit # LessonFormPage      (instructor/admin)
  /courses/:courseId/students             # StudentsPage         (instructor/admin)
  /students                               # AllStudentsPage      (instructor/admin)
  /settings                               # SettingsPage         (admin only)
*                                         # Redirect to /
```

### 6.2 ProtectedRoute

**File**: `components/auth/ProtectedRoute.tsx`

Guards all authenticated routes. Behavior:
1. While `isLoading`: renders skeleton UI
2. If not authenticated: redirects to `/login` (preserves `location` in state for return-after-login)
3. If `user.must_change_password` and not already on `/change-password`: forces redirect
4. If `requiredRole` is specified: checks role hierarchy (`admin` > `instructor` > `student`)

### 6.3 Role-Based Access

- **All authenticated users**: Dashboard, Courses list/detail, Lessons, Assignments, Sandbox, Profile, Change Password
- **Instructors + Admins**: My Courses, Course CRUD, Lesson CRUD, Students management
- **Admin only**: Settings page

Role checking is done inline in `AppRoutes` via `isInstructor` / `isAdmin` flags with `Navigate` fallback.

---

## 7. State Management

### 7.1 Zustand Stores

#### Auth Store (`store/authStore.ts`)

**Persisted** to `localStorage` key `auth-storage`. Partialized: only `user` and `isAuthenticated`.

| State | Type | Description |
|---|---|---|
| `user` | `User \| null` | Current user object |
| `isAuthenticated` | `boolean` | Authentication flag |
| `isLoading` | `boolean` | Loading state for auth operations |
| `error` | `string \| null` | Last error message |

| Action | Description |
|---|---|
| `login(data)` | POST login, store tokens in localStorage, set user |
| `register(data)` | POST register, store tokens, set user |
| `logout()` | POST logout (send refresh token), clear tokens + user |
| `fetchUser()` | GET /auth/me/ using stored access token, set user or clear on failure |
| `updateUser(data)` | PATCH /auth/me/, update user in store |
| `clearError()` | Clear error state |
| `setUser(user)` | Directly set user (for invite flows) |

**Token Management**: Access and refresh tokens stored in `localStorage` as `access_token` and `refresh_token`.

#### Preferences Store (`store/preferencesStore.ts`)

**Persisted** to `localStorage` key `preferences-storage`. Partialized: only `theme` and `locale`.

| State | Type | Description |
|---|---|---|
| `theme` | `'system' \| 'light' \| 'dark'` | User's theme preference |
| `locale` | `'en' \| 'uk'` | User's language preference |
| `resolvedTheme` | `'light' \| 'dark'` | Computed actual theme |

| Action | Description |
|---|---|
| `setTheme(theme)` | Resolve theme, apply CSS class, update state |
| `setLocale(locale)` | Update locale in store |

**Side effects**:
- On rehydration from storage: re-resolves and applies theme class
- Module-level: applies theme class immediately on import
- Media query listener: auto-updates when system preference changes (if theme is `system`)

### 7.2 React Query (Server State)

**Client Config** (`lib/queryClient.ts`):
- `staleTime`: 5 minutes
- `retry`: 1
- `refetchOnWindowFocus`: false

**Query Key Conventions**:
| Pattern | Example |
|---|---|
| `['courses', params]` | Course list |
| `['course', id]` | Single course |
| `['course', id, 'lessons']` | Lessons for a course |
| `['course', id, 'modules']` | Modules for a course |
| `['course', id, 'datasets']` | Datasets for a course |
| `['course', id, 'assignments']` | Assignments for a course |
| `['course', id, 'enrollments']` | Enrollments for a course |
| `['lesson', courseId, lessonId]` | Single lesson |
| `['lesson', courseId, lessonId, 'submissions']` | Submissions for a lesson |
| `['assignment', courseId, assignmentId]` | Single assignment |
| `['assignment', courseId, assignmentId, 'submissions', 'my']` | My submissions |
| `['enrollments', 'my']` | My enrollments |
| `['sandbox', 'database-types']` | Database types (staleTime: Infinity) |
| `['sandbox', 'datasets', dbType]` | Sandbox datasets |
| `['progress', 'my']` | My overall progress |
| `['attachments', courseId, lessonId]` | Lesson attachments |

**Mutation Invalidation**: All mutations use `onSuccess` to invalidate relevant query keys.

---

## 8. Pages

### 8.1 LoginPage (`pages/auth/LoginPage.tsx`)

**Layout**: Split-screen. Left: dark decorative panel with SQL code snippet (lg+ only). Right: login form.

**Components**: Card (glass), Input, Label, Button, Alert, Spinner, Database icon.

**Form**: `react-hook-form` + `zodResolver(loginSchema)`. Fields: email, password.

**API**: `useAuthStore().login()` -> POST `/auth/login/`.

**Features**: Redirects to previous location after login. Mobile-only branding header. Animated fade-in.

### 8.2 RegisterPage (`pages/auth/RegisterPage.tsx`)

**Layout**: Same split-screen as login. Left panel shows CREATE TABLE + INSERT SQL.

**Components**: Same as login + Progress (password strength).

**Form**: `registerSchema`. Fields: first_name, last_name, email, password, password_confirm.

**Features**: Real-time password strength indicator (weak/fair/strong) with color-coded Progress bar.

**API**: `useAuthStore().register()` -> POST `/auth/register/`.

### 8.3 ChangePasswordPage (`pages/auth/ChangePasswordPage.tsx`)

**Layout**: Centered card. Adapts between "Change Password" and "Set Password" modes.

**Logic**: If `user.must_change_password` is true, uses `authApi.setPassword()` (no old password required). Otherwise uses `authApi.changePassword()` (requires old password).

**Form**: `changePasswordSchema`. Fields: old_password (conditional), new_password, new_password_confirm.

### 8.4 DashboardPage (`pages/dashboard/DashboardPage.tsx`)

**Data**: `useCourses({ is_published: true })`, `useMyProgress()`.

**Layout**:
1. Welcome banner (gradient from-primary/10 to-primary/5, personalized greeting)
2. Stats grid (4 columns on lg): Enrolled Courses, Completed, In Progress, Avg Score
3. Course progress card with enrolled courses, progress bars, links

**Components**: `StatCard` (with icons), `Card`, `Badge`, `Progress`, `Skeleton` (loading state).

**Empty State**: Centered icon + "Browse Courses" CTA when no enrollments.

### 8.5 CoursesListPage (`pages/courses/CoursesListPage.tsx`)

**Data**: `useCourses({ is_published: true })`.

**Features**: Search input (client-side filtering by title/description/instructor), "Create Course" button (instructors only), responsive grid (md:2 cols, lg:3 cols).

**Components**: Card grid with GraduationCap icon, database_type badge, student count, lesson count, enrolled badge.

### 8.6 CourseDetailPage (`pages/courses/CourseDetailPage.tsx`)

**Data**: `useCourse(courseId)`, `useLessons(courseId)`, `useModules(courseId)`.

**Layout**: 3-column grid (2+1). Left: About card + Lessons list. Right: Course info card + Enrollment/Progress card.

**Features**:
- Lessons grouped by modules (if any) with type icons (BookOpen/Code/Layers)
- Completion status per lesson (CheckCircle/Clock/Play)
- Enrollment with optional key
- Unenroll with confirmation dialog
- Progress bar for enrolled students
- "Manage" button for course owners

**Components**: Dialog (unenroll confirmation), Progress, Badge, Spinner.

### 8.7 LessonPage (`pages/lessons/LessonPage.tsx`)

**Data**: `useLesson()`, `useLessonSubmissions()`, `useAttachments()`, `useSubmitLesson()`.

**Layout**: Theory/Practice tabs for mixed lessons. Two-column grid for practice: task + hints on left, editor + results on right.

**Features**:
- Markdown rendering with `react-markdown`
- **Inline SQL exercises**: detects `language-sql-exercise` code blocks, parses JSON config, renders `SqlExerciseBlock`
- Client-side SQLite preview (instant results via WASM for sqlite courses)
- Server-side grading with score/feedback display
- Hints with pagination
- Dataset schema display
- File attachments list with download links
- Attempt counting with max_attempts limit

**Components**: SqlEditor, SqlExerciseBlock, Tabs, Table, Badge, Alert, Spinner.

### 8.8 AssignmentPage (`pages/assignments/AssignmentPage.tsx`)

**Data**: `useAssignment()`, `useMySubmissions()`, `useSubmitAssignment()`.

**Layout**: Two-column grid. Left: Instructions + Hints + Dataset. Right: Editor + Results + Submission History.

**Features**:
- Difficulty badge (color-coded: easy=secondary, medium=outline, hard=destructive)
- Instant SQLite preview + server grading
- Feedback display: keywords missing, forbidden keywords used
- Submission history (last 5 attempts)

### 8.9 SandboxPage (`pages/sandbox/SandboxPage.tsx`)

**Data**: `useDatabaseTypes()`, `useSandboxDatasets()`.

**Layout**: 3-column grid. Left (1 col): DB type selector + dataset selector + schema editors. Right (2 cols): query editor + results.

**Features**:
- Database type selection (PostgreSQL, SQLite, MySQL, MariaDB, MongoDB, Redis)
- Dataset presets or custom schema
- **Dual execution**: SQLite runs client-side via sql.js WASM; other DBs run server-side with session management
- Session persistence across queries (session_id + schema init on first query)
- Session reset capability
- Quick start examples (Basic SELECT, GROUP BY, JOIN)
- Results table with up to 100 rows displayed
- Language switching for MongoDB (JavaScript) and Redis (plaintext)

### 8.10 ProfilePage (`pages/profile/ProfilePage.tsx`)

**Data**: `useAuthStore()`.

**Layout**: Centered max-w-2xl. Avatar + heading. Personal info card (view/edit toggle). Security card.

**Features**: Inline editing for first_name/last_name. Success alert with 3-second auto-dismiss.

### 8.11 SettingsPage (`pages/admin/SettingsPage.tsx`)

**Layout**: 2-column grid of status cards.

**Cards**: System Status (API/DB/Sandbox pool), Database Info (type/host/name), Quick Actions (Django Admin/API Browser links), Configuration info.

### 8.12 MyCoursesPage (`pages/instructor/MyCoursesPage.tsx`)

**Data**: `useCourses()` (all, not just published).

**Features**: Course cards with Published/Draft badges, student count, lesson count, Manage/Duplicate/View buttons.

### 8.13 CourseFormPage (`pages/instructor/CourseFormPage.tsx`)

**Form**: `courseSchema`. Handles both create and edit (detects `courseId` param).

**Fields**: Title, Description (Textarea), Database Type (Select from 6 options), Start/End Dates, Enrollment Key, Max Students.

**API**: `useCreateCourse()` or `useUpdateCourse()`.

### 8.14 CourseManagePage (`pages/instructor/CourseManagePage.tsx`)

**Data**: `useCourse()`, `useLessons()`, `useModules()`.

**Features**:
- Publish/Unpublish course toggle
- Course duplication
- Module management: add, delete, toggle publish, with GripVertical for reordering (UI only)
- Lesson list: numbered, type badges, publish toggle, edit/delete with confirmation dialogs
- Add lesson button linking to LessonFormPage

### 8.15 LessonFormPage (`pages/instructor/LessonFormPage.tsx`)

**Form**: `lessonSchema`. Most complex form in the app.

**Sections**:
1. Basic Info: title, description, lesson_type (radio cards: theory/practice/mixed), module (optional select)
2. Theory Content (if applicable): Monaco editor with Markdown language
3. Practice Task (if applicable): dataset select, task description, initial code (Monaco), expected query (Monaco), scoring params (max_score, time_limit, max_attempts)
4. Hints: dynamic list, add/remove
5. Attachments (edit mode only): FileUpload + attachment list with delete
6. Publish toggle (Switch)

**API**: `useCreateLesson()` or `useUpdateLesson()`, `useUploadAttachment()`, `useDeleteAttachment()`.

### 8.16 StudentsPage (`pages/instructor/StudentsPage.tsx`)

**Data**: `useCourse()`, `useCourseEnrollments()`.

**Features**: Search filter, enrollment list with Avatar, email, enrollment date, status badge, optional grade display.

### 8.17 AllStudentsPage (`pages/instructor/AllStudentsPage.tsx`)

**Data**: `useCourses()`, then fetches enrollments for each course in parallel.

**Features**: Aggregates students across all instructor's courses, deduplicates by student ID, shows course badges per student, search filter.

---

## 9. Monaco Editor

### 9.1 SqlEditor Component

**File**: `components/editor/SqlEditor.tsx`

**Props**:

| Prop | Type | Default | Description |
|---|---|---|---|
| `value` | `string` | -- | Editor content |
| `onChange` | `(value: string) => void` | -- | Change handler |
| `language` | `'sql' \| 'javascript' \| 'redis' \| 'markdown'` | `'sql'` | Editor language |
| `height` | `string` | `'160px'` | Editor height |
| `readOnly` | `boolean` | `false` | Read-only mode |
| `onExecute` | `() => void` | -- | Ctrl+Enter callback |
| `placeholder` | `string` | -- | Placeholder text |
| `className` | `string` | -- | Wrapper class |

**Features**:
- Custom SQL keyword completion provider (80+ keywords)
- `Ctrl+Enter` / `Cmd+Enter` keybinding for execution
- Auto-focus on mount
- Theme-aware (switches between `noble-dark` and `noble-light`)
- Font: JetBrains Mono, Fira Code, Cascadia Code, Consolas (fallback chain)
- Font size: 13px
- Tab size: 2
- Word wrap: on
- Minimap: disabled
- Folding: disabled
- Auto layout: enabled
- Custom scrollbar: 8px

### 9.2 Custom Themes

**File**: `components/editor/monacoThemes.ts`

Two themes: `noble-dark` (based on `vs-dark`) and `noble-light` (based on `vs`).

**noble-dark colors**:
| Monaco Color | Hex |
|---|---|
| `editor.background` | `#1d1f18` |
| `editor.foreground` | `#c8d1bc` |
| `editor.lineHighlightBackground` | `#252820` |
| `editor.selectionBackground` | `#839a6440` |
| `editorCursor.foreground` | `#839a64` |
| `editorLineNumber.foreground` | `#8a8b8c` |
| `editorLineNumber.activeForeground` | `#c8d1bc` |

**noble-dark token rules**:
| Token | Color | Style |
|---|---|---|
| comment | `#8a8b8c` | italic |
| string | `#c8d1bc` | -- |
| keyword | `#839a64` | bold |
| number | `#db574a` | -- |
| function | `#839a64` | -- |
| operator | `#8a8b8c` | -- |
| identifier | `#c8d1bc` | -- |

**noble-light colors**:
| Monaco Color | Hex |
|---|---|
| `editor.background` | `#f5f5f0` |
| `editor.foreground` | `#2a2d24` |
| `editor.lineHighlightBackground` | `#eef0e8` |
| `editor.selectionBackground` | `#839a6430` |
| `editorCursor.foreground` | `#839a64` |

**noble-light token rules**: Same structure; keyword = `#566b38`, string = `#5a6848`, number = `#c44a3e`.

### 9.3 SqlExerciseBlock

**File**: `components/editor/SqlExerciseBlock.tsx`

Embeddable SQL exercise for theory content. Triggered by `\`\`\`sql-exercise` code blocks in Markdown.

**Config** (JSON in code block):
```json
{
  "schema": "CREATE TABLE ...",
  "seed": "INSERT INTO ...",
  "initial": "SELECT ",
  "hint": "Try SELECT * FROM users"
}
```

**Features**:
- Lazy SQLite initialization (on first run)
- Run/Reset/Hint buttons
- Results table (max 20 rows)
- Error display
- Execution time badge
- Affected rows count

---

## 10. Charts

### 10.1 StatCard

**File**: `components/charts/StatCard.tsx`

Dashboard metric card with:
- Label (text-sm muted)
- Value (text-2xl bold)
- Optional subtitle
- Color-coded icon badge (top-right, rounded-full)
- Optional sparkline (Recharts `AreaChart`, bottom-right, 24x10 area)

Uses `glass` + `shadow-noble-sm`, hover `shadow-noble-md`.

### 10.2 ProgressRing

**File**: `components/charts/ProgressRing.tsx`

SVG circular progress indicator.

**Props**: `value` (0-100), `size` (default 48), `strokeWidth` (default 4).

SVG with two circles: background (`--muted`) and foreground (`--primary`, animated `stroke-dashoffset` 0.6s ease-in-out). Center text shows rounded percentage. Font size scales proportionally (`size * 0.24`).

### 10.3 MiniChart

**File**: `components/charts/MiniChart.tsx`

Standalone sparkline area chart.

**Props**: `data` (number[]), `color` (default `hsl(var(--primary))`), `height` (default 40).

Uses Recharts `AreaChart` with linear gradient fill. Returns `null` if fewer than 2 data points. Uses `useId()` for unique gradient IDs.

---

## 11. Forms

### 11.1 Form Library

- **react-hook-form** (7.71.1) for form state management
- **@hookform/resolvers** (5.2.2) with Zod adapter
- **zod** (4.3.6) for schema validation

### 11.2 Validation Schemas (`lib/schemas.ts`)

#### `loginSchema`
```ts
z.object({
  email: z.string().min(1, 'Email is required').email('Invalid email address'),
  password: z.string().min(1, 'Password is required'),
})
```

#### `registerSchema`
```ts
z.object({
  first_name: z.string().optional(),
  last_name: z.string().optional(),
  email: z.string().min(1).email(),
  password: z.string().min(8, 'Password must be at least 8 characters'),
  password_confirm: z.string().min(1),
}).refine(data => data.password === data.password_confirm, {
  message: 'Passwords do not match',
  path: ['password_confirm'],
})
```

#### `changePasswordSchema`
```ts
z.object({
  old_password: z.string().default(''),
  new_password: z.string().min(8),
  new_password_confirm: z.string().min(1),
}).refine(/* passwords match */)
```

#### `courseSchema`
```ts
z.object({
  title: z.string().min(1).max(255),
  description: z.string().default(''),
  database_type: z.string().min(1),
  enrollment_key: z.string().default(''),
  max_students: z.number().positive().optional().nullable(),
  start_date: z.string().default(''),
  end_date: z.string().default(''),
})
```

#### `lessonSchema`
```ts
z.object({
  title: z.string().min(1).max(255),
  description: z.string().default(''),
  lesson_type: z.enum(['theory', 'practice', 'mixed']),
  theory_content: z.string().default(''),
  practice_description: z.string().default(''),
  practice_initial_code: z.string().default(''),
  expected_query: z.string().default(''),
  required_keywords: z.array(z.string()).default([]),
  forbidden_keywords: z.array(z.string()).default([]),
  order_matters: z.boolean().default(false),
  max_score: z.number().positive().default(100),
  time_limit_seconds: z.number().positive().default(60),
  max_attempts: z.number().positive().optional().nullable(),
  hints: z.array(z.string()).default([]),
  dataset_id: z.string().optional().nullable(),
  module_id: z.string().optional().nullable(),
  is_published: z.boolean().default(false),
})
```

#### `moduleSchema`
```ts
z.object({
  title: z.string().min(1).max(255),
  description: z.string().default(''),
  order: z.number().optional(),
  is_published: z.boolean().default(false),
})
```

### 11.3 Inferred Types

Each schema exports its inferred type: `LoginFormData`, `RegisterFormData`, `ChangePasswordFormData`, `CourseFormData`, `LessonFormData`, `ModuleFormData`.

---

## 12. API Layer

### 12.1 Axios Client (`api/client.ts`)

**Base URL**: `VITE_API_URL` env var or `http://localhost:8000`, appended with `/api`.

**Request Interceptor**: Attaches `Authorization: Bearer <access_token>` from localStorage.

**Response Interceptor** (401 handling):
1. If 401 received and not already retrying:
   - Sets `isRefreshing = true`
   - Attempts refresh via `POST /api/auth/token/refresh/` with refresh token
   - On success: stores new access token, retries original request + all queued requests
   - On failure: clears tokens, redirects to `/login`
2. If 401 while already refreshing: queues the request in `failedQueue`
3. Queue is processed after refresh completes or fails

### 12.2 API Modules

#### `auth.ts`
| Method | Endpoint | Description |
|---|---|---|
| `login(data)` | POST `/auth/login/` | Returns `AuthResponse` (user + tokens) |
| `register(data)` | POST `/auth/register/` | Returns `AuthResponse` |
| `logout(refresh?)` | POST `/auth/logout/` | Blacklists refresh token |
| `getMe()` | GET `/auth/me/` | Returns `User` |
| `updateMe(data)` | PATCH `/auth/me/` | Returns updated `User` |
| `changePassword(data)` | POST `/auth/change-password/` | Void |
| `setPassword(data)` | POST `/auth/set-password/` | Void (for must_change_password) |
| `acceptInvite(data)` | POST `/auth/invite/accept/` | Returns `AuthResponse` |
| `checkInvite(token)` | GET `/auth/invite/check/:token/` | Returns `InviteCheckResponse` |
| `refreshToken(refresh)` | POST `/auth/token/refresh/` | Returns `{ access }` |

#### `courses.ts`
| Method | Endpoint | Description |
|---|---|---|
| `list(params?)` | GET `/courses/` | Paginated list, optional search/is_published filter |
| `get(id)` | GET `/courses/:id/` | Single course |
| `create(data)` | POST `/courses/` | Create course |
| `update(id, data)` | PATCH `/courses/:id/` | Update course |
| `delete(id)` | DELETE `/courses/:id/` | Delete course |
| `enroll(id, key?)` | POST `/courses/:id/enroll/` | Enroll with optional key |
| `unenroll(id)` | POST `/courses/:id/unenroll/` | Unenroll |
| `getEnrollments(id)` | GET `/courses/:id/enrollments/` | Course enrollments |
| `getMyEnrollments()` | GET `/enrollments/` | My enrollments (paginated) |
| `getDatasets(courseId)` | GET `/courses/:id/datasets/` | Course datasets |
| `createDataset(courseId, data)` | POST `/courses/:id/datasets/` | Create dataset |
| `updateDataset(courseId, dsId, data)` | PATCH `/courses/:id/datasets/:dsId/` | Update dataset |
| `deleteDataset(courseId, dsId)` | DELETE `/courses/:id/datasets/:dsId/` | Delete dataset |
| `duplicate(courseId, title?)` | POST `/courses/:id/duplicate/` | Duplicate course |

#### `lessons.ts`
| Method | Endpoint | Description |
|---|---|---|
| `list(courseId)` | GET `/courses/:id/lessons/` | Paginated lessons |
| `get(courseId, id)` | GET `/courses/:id/lessons/:id/` | Single lesson |
| `create(courseId, data)` | POST `/courses/:id/lessons/` | Create lesson |
| `update(courseId, id, data)` | PATCH `/courses/:id/lessons/:id/` | Update lesson |
| `delete(courseId, id)` | DELETE `/courses/:id/lessons/:id/` | Delete lesson |
| `reorder(courseId, ids)` | POST `/courses/:id/lessons/reorder/` | Reorder lessons |
| `submit(courseId, lessonId, query)` | POST `/courses/:id/lessons/:id/submissions/` | Submit query |
| `getMySubmissions(courseId, lessonId)` | GET `/courses/:id/lessons/:id/submissions/my_submissions/` | My submissions |

#### `modules.ts`
| Method | Endpoint | Description |
|---|---|---|
| `list(courseId)` | GET `/courses/:id/modules/` | All modules |
| `get(courseId, id)` | GET `/courses/:id/modules/:id/` | Single module |
| `create(courseId, data)` | POST `/courses/:id/modules/` | Create module |
| `update(courseId, id, data)` | PATCH `/courses/:id/modules/:id/` | Update module |
| `delete(courseId, id)` | DELETE `/courses/:id/modules/:id/` | Delete module |
| `reorder(courseId, ids)` | POST `/courses/:id/modules/reorder/` | Reorder modules |

#### `assignments.ts`
| Method | Endpoint | Description |
|---|---|---|
| `list(courseId, params?)` | GET `/courses/:id/assignments/` | Paginated assignments |
| `get(courseId, id)` | GET `/courses/:id/assignments/:id/` | Single assignment |
| `create(courseId, data)` | POST `/courses/:id/assignments/` | Create assignment |
| `update(courseId, id, data)` | PATCH `/courses/:id/assignments/:id/` | Update assignment |
| `delete(courseId, id)` | DELETE `/courses/:id/assignments/:id/` | Delete assignment |
| `reorder(courseId, ids)` | POST `/courses/:id/assignments/reorder/` | Reorder assignments |

#### `submissions.ts`
| Method | Endpoint | Description |
|---|---|---|
| `submit(courseId, assignmentId, data)` | POST `/courses/:cid/assignments/:aid/submissions/` | Submit query |
| `list(courseId, assignmentId)` | GET `/courses/:cid/assignments/:aid/submissions/` | All submissions |
| `get(courseId, assignmentId, id)` | GET `/courses/:cid/assignments/:aid/submissions/:id/` | Single submission |
| `getMySubmissions(courseId, assignmentId)` | GET `/courses/:cid/assignments/:aid/submissions/my/` | My submissions |
| `getMyResults(courseId)` | GET `/courses/:id/results/my/` | My results for course |
| `getAllResults(courseId)` | GET `/courses/:id/results/` | All results (instructor) |
| `getMyProgress()` | GET `/results/my_progress/` | Progress across all courses |
| `getCourseProgress(courseId)` | GET `/results/my_progress/?course=:id` | Progress for single course |

#### `sandbox.ts`
| Method | Endpoint | Description |
|---|---|---|
| `getDatabaseTypes()` | GET `/sandbox/database-types/` | Available DB types |
| `getDatasets(dbType?)` | GET `/sandbox/datasets/` | Available datasets |
| `executeQuery(request)` | POST `/sandbox/execute/` | Execute query |
| `resetSession(sessionId)` | POST `/sandbox/session/reset/` | Reset sandbox session |

#### `attachments.ts`
| Method | Endpoint | Description |
|---|---|---|
| `list(courseId, lessonId)` | GET `/courses/:cid/lessons/:lid/attachments/` | List attachments |
| `upload(courseId, lessonId, file)` | POST `/courses/:cid/lessons/:lid/attachments/` | Upload (multipart/form-data) |
| `delete(courseId, lessonId, attId)` | DELETE `/courses/:cid/lessons/:lid/attachments/:aid/` | Delete attachment |

### 12.3 TypeScript Types (`types/index.ts`)

| Interface | Key Fields |
|---|---|
| `User` | id, email, first_name, last_name, full_name, role, must_change_password, is_active |
| `AuthTokens` | access, refresh |
| `AuthResponse` | user, tokens |
| `Course` | id, title, description, instructor, database_type, is_published, enrollment_key, student_count, assignment_count, lesson_count, is_enrolled, datasets |
| `Dataset` | id, name, description, schema_sql, seed_sql, is_default |
| `Assignment` | id, title, description, instructions, query_type, difficulty, expected_query, expected_result, required_keywords, forbidden_keywords, max_score, hints, due_date, is_published |
| `Submission` | id, query, status, result, error_message, execution_time_ms, score, is_correct, feedback, attempt_number |
| `QueryResult` | columns, rows, row_count |
| `SubmissionFeedback` | result_match, keywords_found, keywords_missing, forbidden_used, hints, message |
| `UserResult` | best_submission, best_score, total_attempts, is_completed |
| `Enrollment` | student, course, status, grade, enrolled_at |
| `CourseProgress` | total_assignments, completed_assignments, total_score, max_possible_score, completion_rate, percentage_score |
| `PaginatedResponse<T>` | count, next, previous, results |

### 12.4 Client-Side SQLite (`lib/sqljs.ts` + `hooks/useSqlite.ts`)

**WASM loader** (`sqljs.ts`):
- Singleton: loads `sql.js` WASM once, caches the promise
- `locateFile` points to `/sql-wasm.wasm` (public directory)
- `createDatabase(schema?, seed?)`: creates in-memory DB, runs schema + seed SQL
- `executeQuery(db, query)`: executes query, returns `LocalQueryResult` matching server API shape

**React hook** (`useSqlite.ts`):
- Manages DB lifecycle via ref
- `initDatabase(schema, seed)`: creates fresh DB, returns `{ success, error? }`
- `execute(query)`: runs query against current DB
- `reset()`: re-initializes with stored schema/seed
- Auto-closes DB on unmount

---

## 13. Design Tokens

### 13.1 Complete Color Palette

#### Core Colors (Light / Dark)

| Token | Light HSL | Dark HSL | Usage |
|---|---|---|---|
| background | 70 15% 96% | 70 8% 11% | Page background |
| foreground | 70 10% 12% | 80 15% 85% | Default text |
| card | 0 0% 100% | 70 8% 14% | Card surfaces |
| popover | 0 0% 100% | 70 8% 14% | Dropdown/dialog surfaces |
| primary | 90 25% 49% | 90 25% 49% | Brand color (olive green) |
| secondary | 80 15% 92% | 70 8% 18% | Secondary surfaces |
| muted | 80 10% 93% | 70 6% 18% | Muted backgrounds |
| muted-foreground | 0 1% 54% | 0 1% 54% | Muted/placeholder text |
| accent | 80 18% 82% | 80 18% 30% | Accent highlights |
| destructive | 5 60% 52% | 5 60% 45% | Error/danger (red) |
| success | 90 25% 49% | 90 30% 45% | Success (green) |
| warning | 40 80% 55% | 40 80% 50% | Warning (amber) |
| border | 70 12% 88% | 70 6% 22% | Borders |
| input | 70 12% 88% | 70 6% 22% | Input borders |
| ring | 90 25% 49% | 90 25% 49% | Focus rings |

#### Chart Colors

| Token | Light HSL | Dark HSL |
|---|---|---|
| chart-1 | 90 25% 49% | 90 30% 55% |
| chart-2 | 5 60% 52% | 5 65% 55% |
| chart-3 | 200 40% 50% | 200 50% 55% |
| chart-4 | 40 80% 55% | 40 85% 58% |
| chart-5 | 280 40% 55% | 280 50% 60% |

### 13.2 Border Radius

| Token | Value |
|---|---|
| `--radius` | 0.75rem (12px) |
| `radius-sm` | calc(0.75rem - 4px) = 8px |
| `radius-md` | calc(0.75rem - 2px) = 10px |
| `radius-lg` | 0.75rem = 12px |
| `radius-xl` | calc(0.75rem + 4px) = 16px |
| `radius-2xl` | calc(0.75rem + 8px) = 20px |

### 13.3 Shadows

All shadows use the theme-aware `--shadow-color` variable:

| Utility | Layers |
|---|---|
| `shadow-noble-sm` | `0 1px 2px 0 (4%)`, `0 1px 3px 0 (6%)` |
| `shadow-noble` | `0 2px 4px 0 (4%)`, `0 4px 12px 0 (8%)` |
| `shadow-noble-md` | `0 4px 6px -1px (6%)`, `0 6px 16px -2px (10%)` |
| `shadow-noble-lg` | `0 10px 15px -3px (8%)`, `0 12px 24px -4px (12%)` |

### 13.4 Animation Keyframes

| Name | From | To | Duration |
|---|---|---|---|
| `fadeIn` | opacity: 0 | opacity: 1 | 300ms ease-out |
| `slideUp` | opacity: 0, translateY(8px) | opacity: 1, translateY(0) | 300ms ease-out |
| `scaleIn` | opacity: 0, scale(0.95) | opacity: 1, scale(1) | 200ms ease-out |

### 13.5 Typography

- **Font family**: System default (Tailwind's `font-sans`), no custom font loaded
- **Monospace (editor)**: JetBrains Mono > Fira Code > Cascadia Code > Consolas > monospace
- **Antialiasing**: `antialiased` on body

---

## 14. Responsive Design

### 14.1 Breakpoints

Uses Tailwind CSS v4 default breakpoints:

| Prefix | Min Width |
|---|---|
| `sm` | 640px |
| `md` | 768px |
| `lg` | 1024px |
| `xl` | 1280px |

### 14.2 Mobile vs Desktop Behavior

| Feature | Mobile | Desktop (md+) |
|---|---|---|
| **Sidebar** | Full-width overlay (w-72), slide in/out, backdrop blur | Fixed icon-only (w-16), expands to w-56 on hover |
| **Header** | Hamburger menu visible, logo text hidden | Menu button hidden, full logo with text |
| **Content padding** | px-6 py-8 | px-10 py-10, pl-16 (sidebar offset) |
| **Content max-width** | Full width | max-w-7xl centered |
| **Course grid** | 1 column | md:2 cols, lg:3 cols |
| **Dashboard stats** | 1-2 columns | sm:2 cols, lg:4 cols |
| **Lesson practice** | Stacked vertically | lg:2 column grid |
| **Sandbox** | Stacked vertically | lg:3 column grid (1+2) |
| **Auth pages** | Full-width form, decorative panel hidden | Split 50/50 (decorative + form) |
| **Dialog footer** | Stacked (flex-col-reverse) | Horizontal (sm:flex-row) |
| **Profile form** | Single column | sm:grid-cols-2 for name fields |
| **Input text size** | text-base (16px, prevents iOS zoom) | md:text-sm |

### 14.3 Key Responsive Patterns

1. **Sidebar collapse**: The desktop sidebar uses CSS group hover (`group/sidebar`) to manage icon/label visibility. Labels have `opacity-0 group-hover/sidebar:opacity-100` with a 75ms delay for smooth reveal.

2. **Mobile menu**: Controlled by `sidebarOpen` state in MainLayout. Backdrop click and close button both trigger `onClose`.

3. **Grid breakpoints**: Most grids use `md:grid-cols-2 lg:grid-cols-3` for course lists, and `lg:grid-cols-2` for lesson/assignment two-panel layouts.

4. **Text scaling**: Inputs use `text-base` on mobile (preventing iOS auto-zoom) and `md:text-sm` on desktop.

5. **Hidden elements**: Desktop-only elements use `hidden md:flex` or `hidden lg:flex`. Mobile-only elements use `md:hidden` or `lg:hidden`.

---

*End of specification.*
