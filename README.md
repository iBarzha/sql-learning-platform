sad# SQL Learning Platform

An interactive platform for learning SQL and NoSQL databases with real-time query execution and automated grading.

## Features

- **Multi-database support**: PostgreSQL, MySQL, MariaDB, MongoDB, Redis
- **Interactive SQL Editor**: Monaco-based editor with syntax highlighting
- **Automated Grading**: Query evaluation with hints and feedback
- **Course Management**: Create courses, assignments, and datasets
- **Warm Pool Architecture**: Pre-initialized Docker containers for fast query execution
- **Role-based Access**: Students and Instructors with different permissions

## Tech Stack

### Backend
- Django 5 + Django REST Framework
- SimpleJWT for authentication
- PostgreSQL (main database)
- Docker SDK for Python

### Frontend
- React 18 + TypeScript
- Vite
- TailwindCSS + shadcn/ui
- Zustand for state management
- Monaco Editor

### Infrastructure
- Docker & Docker Compose
- Nginx
- PostgreSQL, MySQL, MariaDB containers for sandboxing
- MongoDB, Redis containers for NoSQL

## Project Structure

```
sql-learning-platform/
├── backend/
│   ├── config/              # Django settings
│   ├── users/               # User, Invite models
│   ├── courses/             # Course, Enrollment, Dataset
│   ├── assignments/         # Assignment model
│   ├── submissions/         # Submission, UserResult
│   ├── sandbox/             # Docker warm pool manager
│   ├── grading/             # Query evaluator
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── api/             # Axios client
│   │   ├── components/      # UI components
│   │   ├── pages/           # Page components
│   │   ├── hooks/           # Custom hooks
│   │   ├── store/           # Zustand stores
│   │   └── lib/             # Utilities
│   └── package.json
├── docker/                  # Docker configurations
├── nginx/                   # Nginx configuration
└── docker-compose.yml
```

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 18+
- Docker & Docker Compose
- PostgreSQL

### Development Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd sql-learning-platform
```

2. Backend setup:
```bash
cd backend
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

3. Frontend setup:
```bash
cd frontend
npm install
npm run dev
```

4. Start Docker services:
```bash
docker-compose up -d
```

## Git Workflow

- `main` - Production branch
- `develop` - Development branch
- `feature/*` - Feature branches

## License

MIT
