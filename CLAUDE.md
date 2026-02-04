# CLAUDE.md - Project Guidelines for AI Assistant

## Project Overview
SQL Learning Platform - Interactive platform for learning SQL and NoSQL databases.
- Backend: Django 5 + DRF + SimpleJWT
- Frontend: React 18 + TypeScript + Vite + TailwindCSS + shadcn/ui
- Database: PostgreSQL + Docker sandbox containers

---

## Code Style Guidelines

### General Principles
- Write clean, readable, self-documenting code
- Follow DRY (Don't Repeat Yourself) principle
- Keep functions small and focused (single responsibility)
- Use meaningful variable and function names
- Prefer composition over inheritance

### Python/Django
- Follow PEP 8 style guide
- Use type hints where appropriate
- Use docstrings for public functions and classes
- Imports order: stdlib → third-party → local (separated by blank lines)
- Use f-strings for string formatting
- Max line length: 100 characters

```python
# Good
def get_user_courses(user: User, include_completed: bool = False) -> QuerySet[Course]:
    """Retrieve all courses for a given user."""
    queryset = Course.objects.filter(enrollments__student=user)
    if not include_completed:
        queryset = queryset.exclude(enrollments__status='completed')
    return queryset

# Bad
def getCourses(u, ic=False):
    q = Course.objects.filter(enrollments__student=u)
    if not ic: q = q.exclude(enrollments__status='completed')
    return q
```

### TypeScript/React
- Use functional components with hooks
- Use TypeScript strict mode
- Prefer named exports over default exports
- Use interfaces for object shapes, types for unions/primitives
- Destructure props in function parameters
- Use early returns to reduce nesting

```typescript
// Good
interface UserCardProps {
  user: User;
  onSelect: (id: string) => void;
}

export function UserCard({ user, onSelect }: UserCardProps) {
  if (!user) return null;

  return (
    <div onClick={() => onSelect(user.id)}>
      {user.full_name}
    </div>
  );
}

// Bad
export default function UserCard(props: any) {
  return props.user ? <div onClick={() => props.onSelect(props.user.id)}>{props.user.full_name}</div> : null;
}
```

### CSS/Tailwind
- Use Tailwind utility classes
- Extract repeated patterns into components
- Use CSS variables for theme values
- Mobile-first responsive design

---

## Comments Guidelines

### When to Comment
- Complex business logic that isn't obvious
- Workarounds or non-obvious solutions (with explanation WHY)
- TODO items with context
- API endpoints and their purpose

### When NOT to Comment
- Obvious code that is self-explanatory
- Every function or variable
- Commented-out code (delete it instead)

### Comment Style
- Write comments in **English only**
- Use complete sentences with proper punctuation
- Keep comments concise and relevant

```python
# Good: Explains WHY, not WHAT
# Skip weekends as assignment deadlines to give students buffer time
if due_date.weekday() >= 5:
    due_date = due_date + timedelta(days=(7 - due_date.weekday()))

# Bad: States the obvious
# Check if weekday is greater than or equal to 5
if due_date.weekday() >= 5:
```

```typescript
// Good: Documents non-obvious behavior
// Monaco editor requires explicit height, 100% doesn't work in flex containers
<div style={{ height: '400px' }}>

// Bad: Redundant comment
// Set the height to 400px
<div style={{ height: '400px' }}>
```

---

## Git Commit Guidelines

### Commit Message Format
```
<type>: <short description>

[optional body with more details]
```

### Types
- `feat`: New feature
- `fix`: Bug fix
- `refactor`: Code refactoring (no feature change)
- `style`: Formatting, missing semicolons, etc.
- `docs`: Documentation changes
- `test`: Adding or updating tests
- `chore`: Maintenance tasks, dependencies

### Rules
- **DO NOT add Co-Authored-By lines**
- **DO NOT mention AI/Claude in commits**
- Use imperative mood: "Add feature" not "Added feature"
- Keep subject line under 72 characters
- Capitalize first letter
- No period at the end of subject line

### Examples
```
# Good
feat: Add course enrollment with key validation

fix: Prevent duplicate submissions on rapid clicks

refactor: Extract query validation into separate module

# Bad
feat: Added new feature for courses (Co-Authored-By: Claude)

Fixed stuff

WIP
```

---

## File Organization

### Backend Structure
```
backend/
├── config/          # Django settings, main urls
├── users/           # User model, auth
├── courses/         # Course, Enrollment, Dataset
├── assignments/     # Assignment model
├── submissions/     # Submission, UserResult
├── sandbox/         # Docker container management
└── grading/         # Query evaluation logic
```

### Frontend Structure
```
frontend/src/
├── api/             # API client and endpoint functions
├── components/
│   ├── ui/          # Reusable UI components (shadcn)
│   ├── layout/      # Layout components
│   └── features/    # Feature-specific components
├── hooks/           # Custom React hooks
├── pages/           # Page components
├── store/           # Zustand stores
├── types/           # TypeScript interfaces
└── lib/             # Utilities
```

---

## API Design

### REST Conventions
- Use plural nouns: `/api/courses/`, not `/api/course/`
- Use HTTP methods correctly: GET, POST, PUT/PATCH, DELETE
- Return appropriate status codes
- Use nested routes sparingly: `/api/courses/{id}/assignments/`

### Response Format
```json
{
  "id": "uuid",
  "field": "value",
  "created_at": "2024-01-01T00:00:00Z"
}
```

### Error Format
```json
{
  "detail": "Human-readable error message"
}
```

---

## Security Guidelines

- Never commit `.env` files or secrets
- Validate all user input
- Use parameterized queries (Django ORM handles this)
- Sanitize SQL queries in sandbox before execution
- Set appropriate CORS origins
- Use HTTPS in production

---

## Testing

### Backend
- Write unit tests for models and serializers
- Write integration tests for API endpoints
- Use pytest and pytest-django

### Frontend
- Test component rendering and interactions
- Mock API calls in tests
- Use React Testing Library

---

## Branch Naming

```
feature/<description>    # New features
fix/<description>        # Bug fixes
refactor/<description>   # Refactoring
docs/<description>       # Documentation
```

Examples:
- `feature/sql-editor-integration`
- `fix/login-redirect-loop`
- `refactor/submission-service`

---

## Pull Request Guidelines

- Keep PRs focused and small
- Write clear description of changes
- Link related issues if any
- Ensure all tests pass
- Request review when ready

---

## Quick Reference

| Task | Command |
|------|---------|
| Run backend | `cd backend && python manage.py runserver` |
| Run frontend | `cd frontend && npm run dev` |
| Run migrations | `python manage.py migrate` |
| Create migration | `python manage.py makemigrations` |
| Install backend deps | `pip install -r requirements.txt` |
| Install frontend deps | `npm install` |
| Docker up | `docker-compose up -d` |

---

## Remember

1. Code is read more often than written - optimize for readability
2. When in doubt, keep it simple
3. Test your changes before committing
4. Write commits as if explaining to a colleague
5. **No AI attribution in commits or code comments**
