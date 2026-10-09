# SQL Learning Platform — Техническая документация

> Интерактивная веб-платформа для изучения баз данных через практические задания с автоматической проверкой

---

## Содержание

1. [Обзор проекта](#1-обзор-проекта)
2. [Технологический стек](#2-технологический-стек)
3. [Архитектура системы](#3-архитектура-системы)
4. [Backend (Django)](#4-backend-django)
5. [Frontend (React)](#5-frontend-react)
6. [Sandbox-система (изолированное выполнение запросов)](#6-sandbox-система)
7. [Инфраструктура и DevOps](#7-инфраструктура-и-devops)
8. [Безопасность](#8-безопасность)
9. [Система оценивания](#9-система-оценивания)
10. [Интернационализация](#10-интернационализация)
11. [Структура базы данных](#11-структура-базы-данных)
12. [API-эндпоинты](#12-api-эндпоинты)
13. [Процесс развёртывания](#13-процесс-развёртывания)

---

## 1. Обзор проекта

**SQL Learning Platform** — это университетская веб-платформа для изучения баз данных через интерактивные задания с автоматической проверкой. Студенты могут писать и выполнять SQL-запросы прямо в браузере, получая мгновенную обратную связь.

### Ключевые возможности

- **Мультибазовость** — поддержка PostgreSQL, MySQL/MariaDB, MongoDB, Redis и SQLite
- **Интерактивный SQL-редактор** — Monaco Editor (тот же движок, что в VS Code) с подсветкой синтаксиса и автодополнением
- **Автоматическая проверка** — система грейдинга сравнивает результаты запросов студента с эталонными
- **Sandbox-песочница** — безопасное выполнение запросов в изолированных Docker-контейнерах
- **Ролевая модель** — три роли: Admin, Instructor (преподаватель), Student (студент)
- **Двуязычность** — полная поддержка украинского и английского языков
- **Тёмная/светлая тема** — адаптивный интерфейс с поддержкой системных настроек

### Роли пользователей

| Роль | Возможности |
|------|-------------|
| **Student** | Запись на курсы, выполнение заданий, sandbox, просмотр оценок |
| **Instructor** | Создание курсов/уроков/заданий, управление датасетами, просмотр результатов студентов |
| **Admin** | Управление пользователями, системные настройки, полный доступ |

---

## 2. Технологический стек

### Backend
| Технология | Версия | Назначение |
|------------|--------|------------|
| Python | 3.12 | Язык программирования |
| Django | 6.0.2 | Веб-фреймворк |
| Django REST Framework | 3.16.1 | REST API |
| SimpleJWT | 5.5.1 | JWT-аутентификация |
| PostgreSQL | 16 | Основная база данных |
| Gunicorn | 25.0.1 | WSGI HTTP-сервер |
| Docker SDK | 7.1.0 | Управление контейнерами |
| psycopg2 | 2.9.11 | Драйвер PostgreSQL |
| PyMySQL | 1.1.2 | Драйвер MySQL/MariaDB |
| pymongo | 4.16.0 | Драйвер MongoDB |
| redis-py | 7.1.0 | Драйвер Redis |

### Frontend
| Технология | Версия | Назначение |
|------------|--------|------------|
| React | 19.2 | UI-фреймворк |
| TypeScript | 5.9 | Типизация |
| Vite | 7.2 | Сборщик и dev-сервер |
| TailwindCSS | 4.1 | CSS-фреймворк (utility-first) |
| shadcn/ui | latest | Библиотека UI-компонентов (25+ компонентов) |
| Zustand | 5.0 | Управление состоянием (клиентское) |
| TanStack React Query | 5.90 | Управление серверным состоянием и кэширование |
| Monaco Editor | 4.7 | Редактор кода (SQL) |
| React Router | 7.13 | Клиентская маршрутизация |
| Axios | 1.13 | HTTP-клиент |
| react-i18next | 16.5 | Интернационализация |
| Zod | 4.3 | Валидация данных |
| React Hook Form | 7.71 | Работа с формами |
| Recharts | 3.7 | Графики и визуализация |
| sql.js | 1.13 | Клиентский SQLite через WebAssembly |
| Sonner | 2.0 | Уведомления (toast) |
| Lucide React | 0.563 | Иконки |

### Инфраструктура
| Технология | Назначение |
|------------|------------|
| Docker + Docker Compose | Контейнеризация всех сервисов |
| Nginx | Обратный прокси-сервер (production) |
| Redis | Хранение сессий sandbox (cross-worker recovery) |

---

## 3. Архитектура системы

### Общая схема

```
┌─────────────────────────────────────────────────────────────────┐
│                        Клиент (Браузер)                         │
│                     React 19 + TypeScript                       │
│              Monaco Editor │ sql.js (WASM SQLite)               │
└──────────────────────────┬──────────────────────────────────────┘
                           │ HTTP/HTTPS
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│                     Nginx (порт 80/443)                          │
│          Обратный прокси │ Статика │ Gzip │ Security Headers     │
└────────┬──────────────────────────────────────────┬──────────────┘
         │ /api/*                                   │ / (статика)
         ▼                                          ▼
┌──────────────────────┐                  ┌──────────────────────┐
│   Django + Gunicorn   │                  │   Собранный React    │
│     (порт 8000)       │                  │      (dist/)         │
│   2 worker-процесса   │                  └──────────────────────┘
└────┬────────┬─────────┘
     │        │
     ▼        ▼
┌─────────┐  ┌──────────────────────────────────────────────────────┐
│ Main DB │  │              Sandbox-слой (изолированная сеть)        │
│PostgreSQL│  │                                                      │
│  (5433) │  │  ┌────────────┐ ┌────────────┐ ┌─────────┐ ┌──────┐ │
└─────────┘  │  │ PostgreSQL │ │  MariaDB   │ │ MongoDB │ │Redis │ │
             │  │  (sandbox) │ │  (sandbox) │ │(sandbox)│ │(sbox)│ │
             │  └────────────┘ └────────────┘ └─────────┘ └──────┘ │
             │                                                      │
             │  ┌──────────────────┐                                │
             │  │  Session Redis   │  (восстановление сессий)       │
             │  └──────────────────┘                                │
             └──────────────────────────────────────────────────────┘
```

### Сетевая изоляция

Проект использует **две Docker-сети**:

1. **sql-learning-network** — основная сеть для приложения (db, backend, frontend, nginx)
2. **sql-learning-sandbox** — изолированная сеть для sandbox-контейнеров

Backend подключён к обеим сетям и является единственным мостом между основным приложением и песочницами.

### Потоки данных

**Аутентификация:**
```
Браузер → POST /api/auth/login/ → Django → JWT access + refresh токены → localStorage
Каждый запрос → Axios interceptor добавляет Bearer token → Backend проверяет JWT
При истечении access token → автоматический refresh → повторный запрос
```

**Выполнение запроса в Sandbox:**
```
Студент пишет SQL → POST /api/sandbox/execute/
  → Query Validator (проверка на инъекции)
  → Pool Manager (получение подключения к контейнеру)
  → DB Executor (выполнение запроса с таймаутом)
  → Результат: {columns, rows, execution_time_ms}
  → Отображение в таблице на фронтенде
```

**Система оценивания:**
```
Студент отправляет решение → POST /api/submissions/
  → Выполнение запроса студента в sandbox
  → Выполнение эталонного запроса
  → GradingService сравнивает результаты
  → Проверка ключевых слов (required/forbidden)
  → Расчёт балла → Сохранение в Submission + UserResult
  → Обратная связь студенту
```

---

## 4. Backend (Django)

### Структура Django-приложений

```
backend/
├── config/              # Конфигурация Django
│   ├── settings.py      # Настройки (DB, JWT, CORS, middleware)
│   ├── urls.py          # Маршрутизация URL
│   ├── permissions.py   # Кастомные permission-классы
│   ├── health.py        # Health check эндпоинты
│   └── wsgi.py          # WSGI точка входа
│
├── users/               # Пользователи и аутентификация
│   ├── models.py        # User (UUID PK, роли, аватар)
│   ├── views.py         # Login, Register, Profile, Invite
│   └── serializers.py   # Сериализация данных
│
├── courses/             # Курсы и учебные материалы
│   ├── models.py        # Course, Module, Lesson, Dataset, Enrollment
│   ├── views.py         # CRUD курсов, запись студентов
│   └── serializers.py   # Вложенные сериализаторы
│
├── assignments/         # Задания
│   ├── models.py        # Assignment (тип, сложность, критерии)
│   └── views.py         # CRUD заданий
│
├── submissions/         # Отправленные решения
│   ├── models.py        # Submission, UserResult
│   └── views.py         # Отправка и просмотр решений
│
├── grading/             # Система оценивания
│   └── models.py        # GradingService (многокритериальная оценка)
│
└── sandbox/             # Система песочниц
    ├── pool.py          # Менеджер пула подключений
    ├── session_manager.py  # Управление сессиями
    ├── query_validator.py  # Валидация запросов (безопасность)
    ├── services.py      # Сервисный слой sandbox
    ├── executors/       # Исполнители для каждой СУБД
    │   ├── postgresql.py
    │   ├── mysql.py
    │   ├── sqlite.py
    │   ├── mongodb.py
    │   └── redis_executor.py
    └── management/commands/  # Django management-команды
```

### Ключевые архитектурные решения Backend

1. **JWT-аутентификация** — access token (30 мин) + refresh token (2 дня) с ротацией и чёрным списком
2. **Ролевая система** — 3 роли (Admin, Instructor, Student) с кастомными permission-классами
3. **Rate limiting** — ограничение частоты запросов (login: 5/мин, submissions: 10/мин, sandbox: 30/мин)
4. **Пул подключений** — "тёплый пул" постоянно работающих контейнеров (без перезапуска)
5. **Без Celery** — отправка email через threading (синхронный подход), без очередей
6. **Без WebSocket** — polling для обновлений в реальном времени

---

## 5. Frontend (React)

### Структура страниц и маршрутизация

```
frontend/src/
├── pages/
│   ├── auth/
│   │   ├── LoginPage.tsx          # Вход в систему
│   │   ├── RegisterPage.tsx       # Регистрация
│   │   └── ChangePasswordPage.tsx # Смена пароля
│   │
│   ├── dashboard/
│   │   └── DashboardPage.tsx      # Главная: статистика, прогресс курсов
│   │
│   ├── courses/
│   │   ├── CoursesListPage.tsx    # Каталог курсов, поиск, запись
│   │   └── CourseDetailPage.tsx   # Детали курса: модули, уроки
│   │
│   ├── lessons/
│   │   └── LessonPage.tsx         # Урок: теория + практика (вкладки)
│   │
│   ├── assignments/
│   │   └── AssignmentPage.tsx     # Задание: редактор, результаты, история
│   │
│   ├── sandbox/
│   │   └── SandboxPage.tsx        # Свободная песочница для экспериментов
│   │
│   ├── profile/
│   │   └── ProfilePage.tsx        # Профиль: данные, аватар, безопасность
│   │
│   ├── instructor/                # Только для преподавателей
│   │   ├── MyCoursesPage.tsx      # Мои курсы
│   │   ├── CourseFormPage.tsx     # Создание/редактирование курса
│   │   ├── CourseManagePage.tsx   # Управление содержимым курса
│   │   ├── LessonFormPage.tsx    # Создание/редактирование урока
│   │   ├── StudentsPage.tsx      # Студенты курса
│   │   └── AllStudentsPage.tsx   # Все студенты
│   │
│   └── admin/                     # Только для администраторов
│       ├── SettingsPage.tsx       # Системные настройки
│       └── UserManagementPage.tsx # Управление пользователями
```

### Компонентная архитектура

```
components/
├── ui/                    # 25+ базовых компонентов (shadcn/ui + Radix UI)
│   ├── Button, Input, Label, Textarea
│   ├── Card, Badge, Avatar, Separator
│   ├── Dialog, AlertDialog, Select, Tabs
│   ├── Table, Skeleton, Spinner
│   └── Breadcrumb, Alert, Tooltip
│
├── layout/                # Каркас приложения
│   ├── MainLayout.tsx     # Общий layout (Header + Sidebar + Content)
│   ├── Header.tsx         # Верхняя панель навигации
│   ├── Sidebar.tsx        # Боковая панель (иконки → раскрытие при наведении)
│   ├── ThemeToggle.tsx    # Переключатель темы (система/светлая/тёмная)
│   ├── LanguageSwitcher.tsx  # Переключатель EN/UK
│   └── UserMenu.tsx       # Меню пользователя с аватаром
│
├── editor/                # SQL-редактор
│   ├── SqlEditor.tsx      # Обёртка Monaco Editor (Ctrl+Enter = выполнить)
│   ├── SqlExerciseBlock.tsx  # Встроенные упражнения в уроках
│   └── monacoThemes.ts    # Кастомные темы (noble-dark, noble-light)
│
├── charts/                # Визуализация
│   ├── StatCard.tsx       # Карточка статистики
│   ├── ProgressRing.tsx   # Кольцевой индикатор прогресса
│   └── MiniChart.tsx      # Мини-график (Recharts)
│
└── auth/                  # Аутентификация
    ├── ProtectedRoute.tsx # Защита маршрутов (роль + auth)
    └── AuthLayout.tsx     # Layout для страниц входа/регистрации
```

### Управление состоянием

**Zustand** (клиентское состояние):
- `authStore` — пользователь, токены, login/logout, загрузка аватара
- `preferencesStore` — тема (system/light/dark), язык (en/uk)

**React Query** (серверное состояние):
- Автоматическое кэширование данных (staleTime: 5 минут)
- Дедупликация запросов
- Фоновое обновление данных
- Инвалидация кэша при мутациях

### Стилизация и дизайн-система

- **TailwindCSS 4** — utility-first подход, минимум кастомного CSS
- **CSS-переменные** — 24 цветовых токена в HSL-формате для тем
- **Glass-morphism** — `.glass` и `.glass-heavy` утилиты с backdrop-blur
- **Адаптивность** — breakpoints: sm (640px), md (768px), lg (1024px), xl (1280px)
- **Анимации** — fadeIn, slideUp, scaleIn с CSS @keyframes
- **Anti-flash скрипт** — предотвращение белой вспышки при загрузке тёмной темы

---

## 6. Sandbox-система

Sandbox — это ключевая подсистема, обеспечивающая безопасное выполнение произвольных SQL/NoSQL-запросов студентов.

### Архитектура Warm Pool

В отличие от подхода "контейнер по запросу", используется **тёплый пул** — контейнеры с базами данных **всегда запущены** и готовы к работе:

```
┌───────────────────────────────────────────────────┐
│                    Pool Manager                    │
│                                                    │
│  ┌─────────────┐  ┌─────────────┐  ┌───────────┐ │
│  │  PostgreSQL  │  │   MariaDB   │  │  MongoDB  │ │
│  │  контейнер   │  │  контейнер   │  │ контейнер │ │
│  │  (256 MB)    │  │  (256 MB)    │  │ (256 MB)  │ │
│  └─────────────┘  └─────────────┘  └───────────┘ │
│                                                    │
│  ┌─────────────┐  ┌──────────────────────────────┐│
│  │    Redis     │  │      Session Redis           ││
│  │  контейнер   │  │  (восстановление сессий)     ││
│  │  (64 MB)     │  │  (128 MB)                    ││
│  └─────────────┘  └──────────────────────────────┘│
│                                                    │
│  SQLite — выполняется in-process (без контейнера)  │
└───────────────────────────────────────────────────┘
```

**Общее потребление памяти: ~1.3 ГБ** (при ограничении системы в 4 ГБ)

### Поддерживаемые СУБД

| СУБД | Контейнер | Драйвер | Особенности |
|------|-----------|---------|-------------|
| PostgreSQL | postgres:15-alpine | psycopg2 | Полная поддержка SQL, multi-statement |
| MariaDB | mariadb:10.11 | PyMySQL | MySQL-совместимый синтаксис |
| SQLite | — (in-process) | sql.js (WASM) | Клиентское выполнение в браузере |
| MongoDB | mongo:7.0 | pymongo | NoSQL: find, aggregate, insert, update |
| Redis | redis:7-alpine | redis-py | Key-value: 80+ разрешённых команд |

### Жизненный цикл выполнения запроса

1. Студент вводит запрос в Monaco Editor
2. Frontend отправляет `POST /api/sandbox/execute/`
3. **Query Validator** проверяет запрос на опасные паттерны
4. **Pool Manager** получает подключение к нужному контейнеру
5. **Schema Reset** — DROP/CREATE схемы (не перезапуск контейнера!)
6. **Seed Data** — заполнение тестовыми данными
7. **Executor** выполняет запрос с таймаутом (10 сек)
8. Результат возвращается: `{columns, rows, row_count, execution_time_ms}`
9. Результат отображается в таблице на фронтенде

### Session Manager

- Управляет состоянием сессий через **Redis**
- Поддерживает **cross-worker recovery** — если Gunicorn worker упал, другой подхватит сессию
- Хранит schema_sql, seed_sql, статус выполнения
- Парсит многострочные команды для разных синтаксисов СУБД

---

## 7. Инфраструктура и DevOps

### Docker Compose — 9 сервисов

```yaml
Сервисы:
┌──────────────────┬───────────────────┬────────┬────────┬──────────────────────┐
│ Сервис           │ Образ             │ Порт   │ RAM    │ Назначение           │
├──────────────────┼───────────────────┼────────┼────────┼──────────────────────┤
│ db               │ postgres:15-alpine│ 5433   │ 512 MB │ Основная БД          │
│ backend          │ Python 3.12 (свой)│ 8000   │ 512 MB │ Django + Gunicorn    │
│ frontend         │ node:20-alpine    │ 5173   │ 512 MB │ Vite dev server      │
│ nginx            │ nginx:alpine      │ 80     │ 128 MB │ Обратный прокси      │
│ sandbox-postgres │ postgres:15-alpine│ —      │ 256 MB │ Песочница PostgreSQL  │
│ sandbox-mariadb  │ mariadb:10.11     │ —      │ 256 MB │ Песочница MariaDB    │
│ sandbox-mongodb  │ mongo:7.0         │ —      │ 256 MB │ Песочница MongoDB    │
│ sandbox-redis    │ redis:7-alpine    │ —      │ 64 MB  │ Песочница Redis      │
│ session-redis    │ redis:7-alpine    │ —      │ 128 MB │ Хранение сессий      │
└──────────────────┴───────────────────┴────────┴────────┴──────────────────────┘
```

### Dockerfile Backend (Multi-stage сборка)

```
Этап 1 — Builder:
  FROM python:3.12-slim
  Установка gcc, libpq-dev (компиляция зависимостей)
  pip install → /install

Этап 2 — Runtime:
  FROM python:3.12-slim
  Только runtime-зависимости (libpq5, curl)
  Копирование скомпилированных пакетов из builder
  Непривилегированный пользователь (django:1000)
  collectstatic для сбора статических файлов
  Gunicorn: 2 воркера, таймаут 60 сек
```

### Nginx — обратный прокси

| Маршрут | Назначение | Кэширование |
|---------|------------|-------------|
| `/` | React SPA (index.html) | Без кэша (SPA) |
| `/api/` | Проксирование на Django | Без кэша |
| `/admin/` | Django Admin | Без кэша |
| `/static/` | Статические файлы | 30 дней (immutable) |
| `/media/` | Загруженные файлы | 7 дней |

**Оптимизации:**
- Gzip-сжатие (CSS, JS, JSON, SVG)
- Буферизация: 4 × 256 KB
- Таймауты: 60 сек (connect, send, read)
- Security headers (HSTS, CSP, X-Frame-Options и т.д.)

### Volumes (тома)

| Том | Назначение |
|-----|------------|
| `postgres_data` | Данные основной БД (персистентное хранение) |
| `backend_static` | Собранные статические файлы Django |
| `backend_media` | Загруженные пользователями файлы |
| `session_redis_data` | Данные сессий Redis (персистентное хранение) |

### Health Checks

Каждый сервис имеет проверку здоровья:

- **db** — `pg_isready` (PostgreSQL готов принимать соединения)
- **backend** — `curl /api/ready/` (проверка Django + подключение к БД)
- **frontend** — `wget localhost:5173` (Vite dev server отвечает)
- **sandbox-postgres** — `pg_isready`
- **sandbox-mariadb** — `healthcheck.sh`
- **sandbox-mongodb** — `mongosh --eval "db.runCommand('ping')"`
- **sandbox-redis** — `redis-cli ping`

### Логирование

Все сервисы используют JSON-логирование с ротацией:
- Максимальный размер файла: **10 MB**
- Максимум файлов: **3** (итого ~30 MB на сервис)

---

## 8. Безопасность

### Многоуровневая защита

```
Уровень 1: Frontend
  └─ Валидация форм (Zod), защита маршрутов (ProtectedRoute)

Уровень 2: Nginx
  └─ Security headers, rate limiting, CORS

Уровень 3: Django
  └─ JWT-аутентификация, permission-классы, rate limiting

Уровень 4: Query Validator
  └─ Проверка SQL на опасные паттерны перед выполнением

Уровень 5: Sandbox
  └─ Изолированная Docker-сеть, ограниченные пользователи БД
```

### Query Validator — защита от SQL-инъекций

Перед выполнением каждый запрос проходит валидацию:

**Заблокировано для PostgreSQL (50+ паттернов):**
- Чтение файлов: `pg_read_file`, `pg_read_binary_file`
- Запись файлов: `COPY TO PROGRAM`
- Системные команды: `pg_execute_server_program`
- Привилегии: `pg_shadow`, `pg_authid`
- Конфигурация: `ALTER SYSTEM`, `pg_reload_conf`
- Расширения: `CREATE EXTENSION`
- Функции: `CREATE FUNCTION/PROCEDURE/TRIGGER`

**Заблокировано для MariaDB:**
- `LOAD_FILE`, `INTO OUTFILE`, `INTO DUMPFILE`
- Таблицы привилегий: `mysql.user`, `information_schema`
- `SET GLOBAL`, `GRANT`, `REVOKE`

**Заблокировано для MongoDB:**
- Admin-команды, JavaScript-выполнение
- Управление пользователями, утечка информации
- DNS-операции

**Redis — whitelist-подход:**
- Только 80+ разрешённых команд (strings, keys, hashes, lists, sets, sorted sets, streams, geo, transactions)
- Заблокировано: `FLUSHALL`, `CONFIG`, `SAVE`, `SHUTDOWN`

### Sandbox-изоляция

- **Отдельная Docker-сеть** — sandbox-контейнеры не могут обращаться к основной БД
- **Ограниченный пользователь** `sandbox_student`:
  - `statement_timeout = 10s` (PostgreSQL)
  - `NOCREATEDB`, `NOCREATEROLE`, `NOSUPERUSER`
  - `max_statement_time = 10` (MariaDB)
- **Schema reset** после каждого запроса (DROP/CREATE, не перезапуск)

### JWT-аутентификация

```
Access Token:  30 минут жизни
Refresh Token: 2 дня жизни
Ротация:       При каждом refresh старый токен попадает в чёрный список
```

### Production-настройки Django

```python
SESSION_COOKIE_SECURE = True      # Только HTTPS
SESSION_COOKIE_HTTPONLY = True     # Недоступен из JavaScript
SESSION_COOKIE_SAMESITE = 'Strict'
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000    # 1 год HSTS
SECURE_SSL_REDIRECT = True
```

---

## 9. Система оценивания

### Многокритериальная оценка (GradingService)

Оценка каждого задания складывается из нескольких критериев с весами:

```
┌──────────────────────────────────────────────────┐
│           Итоговый балл (max_score)               │
│                                                    │
│  ┌──────────────────────┐  Вес: 20%               │
│  │ Forbidden Keywords   │  Нет запрещённых слов?   │
│  │ (запрещённые слова)   │  → полный балл           │
│  └──────────────────────┘                          │
│                                                    │
│  ┌──────────────────────┐  Вес: 20%               │
│  │ Required Keywords    │  Есть обязательные слова?│
│  │ (обязательные слова)  │  → частичный/полный      │
│  └──────────────────────┘                          │
│                                                    │
│  ┌──────────────────────┐  Вес: 60%               │
│  │ Result Matching      │  Совпадение результатов? │
│  │ (сравнение данных)    │  Колонки + строки + типы │
│  └──────────────────────┘                          │
└──────────────────────────────────────────────────┘
```

### Что сравнивается при Result Matching

1. **Колонки** — имена столбцов (регистронезависимо)
2. **Количество строк** — совпадение числа записей
3. **Содержимое** — значения с нормализацией:
   - Булевы значения → сравнение as-is
   - Числа с плавающей точкой → округление до 6 знаков
   - NULL → отдельная обработка
   - Строки → регистронезависимое сравнение
4. **Порядок строк** — опционально (`order_matters` флаг)

### Опции задания

| Опция | Описание |
|-------|----------|
| `required_keywords` | Обязательные SQL-конструкции (напр. "JOIN", "GROUP BY") |
| `forbidden_keywords` | Запрещённые конструкции (напр. "SELECT *") |
| `order_matters` | Порядок строк влияет на оценку |
| `partial_match` | Разрешить частичное совпадение |
| `max_score` | Максимальный балл (по умолчанию 100) |
| `max_attempts` | Максимум попыток |
| `time_limit` | Ограничение по времени |
| `hints` | Массив подсказок (JSON) |

### Обратная связь

Студент получает детализированный JSON с:
- Общий балл и максимальный балл
- Флаг `is_correct`
- Какие ключевые слова найдены/не найдены
- Какие запрещённые слова обнаружены
- Расхождения в результатах (если есть)
- Подсказки при неправильном ответе

---

## 10. Интернационализация

### Поддерживаемые языки

- **Українська (uk)** — основной язык интерфейса
- **English (en)** — альтернативный язык

### Система пространств имён (10 namespace × 2 языка = 20 JSON-файлов)

```
i18n/locales/
├── en/
│   ├── common.json      # Навигация, действия, статусы
│   ├── auth.json        # Вход, регистрация, пароли
│   ├── dashboard.json   # Приветствие, статистика
│   ├── courses.json     # Курсы, запись, модули
│   ├── lessons.json     # Уроки, задания, вложения
│   ├── sandbox.json     # Песочница, запросы, результаты
│   ├── instructor.json  # Управление курсами и студентами
│   ├── admin.json       # Администрирование
│   ├── profile.json     # Профиль пользователя
│   └── editor.json      # SQL-редактор: подсказки, кнопки
│
└── uk/
    └── (аналогичная структура)
```

### Переключение языка

- Сохраняется в `preferencesStore` (Zustand → localStorage)
- Атрибут `lang` на `<html>` обновляется автоматически
- При первом посещении — автоопределение языка браузера
- Мгновенное переключение без перезагрузки страницы

---

## 11. Структура базы данных

### ER-диаграмма (основные сущности)

```
┌──────────────┐       ┌──────────────────┐       ┌───────────────┐
│     User     │       │     Course       │       │    Module     │
├──────────────┤       ├──────────────────┤       ├───────────────┤
│ id (UUID)    │──┐    │ id               │──┐    │ id            │
│ email        │  │    │ title            │  │    │ title         │
│ username     │  │    │ description      │  │    │ course_id  ──→│
│ role         │  ├───→│ instructor_id ──→│  │    │ order         │
│ avatar       │  │    │ database_type    │  │    │ is_published  │
│ must_change_ │  │    │ course_code      │  │    └───────────────┘
│   password   │  │    │ is_published     │  │
└──────────────┘  │    │ max_students     │  │    ┌───────────────┐
                  │    └──────────────────┘  ├───→│    Lesson      │
┌──────────────┐  │                          │    ├───────────────┤
│  Enrollment  │  │    ┌──────────────────┐  │    │ id            │
├──────────────┤  │    │   Assignment     │  │    │ title         │
│ user_id   ──→│──┘    ├──────────────────┤  │    │ type (theory/ │
│ course_id ──→│       │ course_id     ──→│──┘    │  practice/mix)│
│ status       │       │ module_id        │       │ module_id     │
│ grade        │       │ dataset_id    ──→│       │ dataset_id ──→│
└──────────────┘       │ expected_query   │       │ theory_content│
                       │ required_keywords│       │ practice_     │
┌──────────────┐       │ forbidden_keywords       │   content     │
│   Dataset    │       │ max_score        │       └───────────────┘
├──────────────┤       │ difficulty       │
│ id           │       │ hints (JSON)     │       ┌───────────────┐
│ name         │       └──────────────────┘       │  Submission   │
│ schema_sql   │                                   ├───────────────┤
│ seed_sql     │       ┌──────────────────┐       │ student_id ──→│
│ db_type      │       │   UserResult     │       │ assignment_id │
│ instructor_id│       ├──────────────────┤       │ lesson_id     │
│ is_default   │       │ user_id       ──→│       │ query         │
└──────────────┘       │ assignment_id    │       │ status        │
                       │ lesson_id        │       │ result (JSON) │
┌──────────────┐       │ best_score       │       │ score         │
│    Invite    │       │ total_attempts   │       │ is_correct    │
├──────────────┤       │ is_completed     │       │ feedback(JSON)│
│ email        │       │ best_submission  │       │ attempt_number│
│ token        │       └──────────────────┘       └───────────────┘
│ role         │
│ course_id    │       ┌──────────────────┐
│ expires_at   │       │   Attachment     │
│ is_used      │       ├──────────────────┤
└──────────────┘       │ lesson_id        │
                       │ file             │
                       │ file_type        │
                       │ uploaded_by      │
                       └──────────────────┘
```

### Ключевые особенности моделей

- **Dataset** — независимая сущность (не привязана жёстко к курсу), может переиспользоваться
- **User** — UUID в качестве первичного ключа, поддержка аватаров
- **Course** — автогенерируемый уникальный код (6 символов, без O/0/I/1 для читаемости)
- **Submission** — хранит полный результат выполнения и детализированную обратную связь
- **UserResult** — агрегированный результат (лучший балл, общее число попыток)

---

## 12. API-эндпоинты

### Аутентификация (`/api/auth/`)

| Метод | URL | Описание | Rate Limit |
|-------|-----|----------|------------|
| POST | `/login/` | Вход (email + пароль → JWT) | 5/мин |
| POST | `/logout/` | Выход (blacklist токена) | — |
| POST | `/token/refresh/` | Обновление access token | — |
| GET | `/me/` | Текущий пользователь | — |
| PATCH | `/me/` | Обновление профиля/аватара | — |
| POST | `/change-password/` | Смена пароля | 5/мин |
| POST | `/set-password/` | Установка пароля (первый вход) | — |
| POST | `/invite/accept/` | Принятие приглашения | 5/мин |
| GET | `/invite/check/{token}/` | Проверка приглашения | — |
| POST | `/admin/create-user/` | Создание пользователя (Admin) | — |
| GET | `/admin/users/` | Список пользователей (Admin) | — |

### Курсы (`/api/courses/`)

| Метод | URL | Описание |
|-------|-----|----------|
| GET | `/` | Список курсов (по роли) |
| POST | `/` | Создание курса (Instructor) |
| GET | `/{id}/` | Детали курса |
| PATCH | `/{id}/` | Обновление курса |
| DELETE | `/{id}/` | Удаление курса |
| GET | `/available/` | Доступные для записи |
| POST | `/{id}/enroll/` | Запись на курс |
| POST | `/join/` | Присоединение по коду |

### Вложенные ресурсы

| Метод | URL | Описание |
|-------|-----|----------|
| GET/POST | `/courses/{id}/modules/` | Модули курса |
| GET/POST | `/courses/{id}/lessons/` | Уроки курса |
| GET/POST | `/courses/{id}/assignments/` | Задания курса |
| GET/POST | `/courses/{id}/datasets/` | Датасеты курса |
| GET | `/courses/{id}/assignments/{id}/stats/` | Статистика задания |
| POST | `/courses/{id}/assignments/{id}/submissions/` | Отправка решения |
| GET | `/courses/{id}/lessons/{id}/attachments/` | Вложения урока |

### Sandbox (`/api/sandbox/`)

| Метод | URL | Описание | Rate Limit |
|-------|-----|----------|------------|
| POST | `/execute/` | Выполнение запроса | 30/мин |
| POST | `/session/reset/` | Сброс сессии | — |
| GET | `/database-types/` | Доступные СУБД | — |
| GET | `/datasets/` | Публичные датасеты | — |
| GET | `/health/` | Здоровье пула | — |
| GET | `/stats/` | Статистика пула | — |

### Health Checks

| Метод | URL | Описание |
|-------|-----|----------|
| GET | `/api/health/` | Быстрая проверка (Django жив) |
| GET | `/api/ready/` | Полная проверка (Django + БД) |

---

## 13. Процесс развёртывания

### Требования

- Docker + Docker Compose
- Python 3.11+ (для локальной разработки без Docker)
- Node.js 18+ (для локальной разработки без Docker)
- PostgreSQL 15+ (основная БД)
- 4 ГБ оперативной памяти минимум

### Быстрый запуск (Development)

```bash
# 1. Клонировать репозиторий
git clone <repo-url>
cd sql-learning-platform

# 2. Запустить все 9 контейнеров
docker compose up -d

# 3. Применить миграции
docker compose exec backend python manage.py migrate

# 4. Создать суперпользователя
docker compose exec backend python manage.py createsuperuser

# 5. Платформа доступна:
#    Frontend: http://localhost:5173
#    Backend:  http://localhost:8000
#    Admin:    http://localhost:8000/admin/
```

### Production-запуск

```bash
# 1. Настроить .env (SECRET_KEY, DEBUG=False, ALLOWED_HOSTS)

# 2. Собрать фронтенд
cd frontend && npm run build

# 3. Запустить с Nginx
docker compose --profile production up -d

# 4. Платформа доступна на порту 80 (Nginx)
```

### Цепочка зависимостей при запуске

```
1. db (PostgreSQL)                    → готов
2. sandbox-postgres, sandbox-mariadb  → готовы
   sandbox-mongodb, sandbox-redis     → готовы
   session-redis                      → готов
3. backend (ждёт все вышестоящие)     → готов
4. frontend                           → готов
5. nginx (ждёт backend + frontend)    → готов
```

### Переменные окружения

| Переменная | По умолчанию | Описание |
|------------|-------------|----------|
| `SECRET_KEY` | dev-key | Секретный ключ Django |
| `DEBUG` | True | Режим отладки |
| `ALLOWED_HOSTS` | localhost | Разрешённые хосты |
| `DB_NAME` | sql_learning | Имя основной БД |
| `DB_USER` | postgres | Пользователь БД |
| `DB_PASSWORD` | postgres | Пароль БД |
| `DB_HOST` | localhost | Хост БД |
| `DB_PORT` | 5432 | Порт БД |
| `CORS_ALLOWED_ORIGINS` | localhost:5173 | Разрешённые фронтенд-домены |
| `SANDBOX_POOL_SIZE` | 3 | Размер пула sandbox |
| `SANDBOX_TIMEOUT` | 30 | Таймаут sandbox (сек) |
| `MAX_QUERY_TIME` | 10 | Макс. время запроса (сек) |

---

## Итого

**SQL Learning Platform** — это полноценная full-stack платформа для обучения работе с базами данных, включающая:

- **9 Docker-контейнеров** с оркестрацией через Docker Compose
- **5 поддерживаемых СУБД** (PostgreSQL, MariaDB, MongoDB, Redis, SQLite)
- **Многоуровневую систему безопасности** (от валидации на фронтенде до изолированных Docker-сетей)
- **Автоматическую проверку заданий** с детализированной обратной связью
- **Ролевую модель** (Admin, Instructor, Student)
- **Двуязычный интерфейс** (украинский, английский)
- **Современный технологический стек** (Django 6, React 19, TypeScript, TailwindCSS 4)
- **Production-ready архитектуру** с Nginx, health checks, логированием и security headers
