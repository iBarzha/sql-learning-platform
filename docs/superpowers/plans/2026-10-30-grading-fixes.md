# Grading Fixes Implementation Plan (problems 2, 3, 4, 5, 6, 7, 12, 13, 14, 15, 19)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the small and medium items of part II of `GRADING_ALGORITHM.md` (the numbered "problems"): order comparison that tolerates ties, a type-only mismatch hint, an opt-in "column order does not matter" switch, more mutation classes and instructor warnings for the dataset check, a required reference query, hidden row previews on timed lessons, course percentage over all published tasks, instructor timer control, regrading and manual scores.

**Architecture:** The grading core (`backend/grading/`) stays pure Python and gains the comparison features (Task 1). The Django layer (`courses`, `submissions`, `assignments`) wires them, adds the model fields, the validation, the progress rewrite and the new instructor endpoints (Tasks 2 and 3). The React app gets the form switch, the validation errors, the warnings display and the instructor tools (Task 4). Documentation is updated last (Task 5).

**Tech Stack:** Django 6 + DRF, sqlglot 30, React 18 + TypeScript + react-hook-form + zod + TanStack Query, shadcn/ui, react-i18next.

**Spec:** `GRADING_ALGORITHM.md` part I (current behaviour, the authority on the grading model) and part II (the problems being fixed; each entry describes the intended fix). The criteria model is further specified in `docs/superpowers/specs/2026-10-09-criteria-grading-design.md`.

## Global Constraints

- Work in `D:\VIBE_MAX\sql-learning-platform` on branch `feature/admin-dashboard`. Never touch `coursework/`, `server-backup/`, `remote_exec.py`, `.env*`.
- Backend tests: `cd backend && PYTHONIOENCODING=utf-8 .venv/Scripts/python manage.py test <app> --settings=config.settings_test --noinput` (SQLite in memory, rate limits off). The full suite (`manage.py test --settings=config.settings_test`) is 472 tests OK before this plan and must stay green; the 4 engine-integration classes skip without Docker, that is expected. Docker is not available locally: do not try to start sandboxes.
- Frontend checks: `cd frontend && npm run build` must pass (vite build, zero errors). `npx tsc -b --noEmit` has 9 pre-existing errors in `SettingsPage.tsx`, `ChangePasswordPage.tsx`, `RegisterPage.tsx`, `CourseFormPage.tsx` (2) and `LessonFormPage.tsx` (3, zod resolver typing); `npm run lint` has 6 pre-existing `react-refresh/only-export-components` errors in `src/components/ui/*`. Do not add new tsc or eslint errors; do not try to fix the pre-existing ones.
- Scoring model is binary criteria + threshold (`backend/grading/criteria.py`): score is `max_score` when `passed_count >= threshold`, else 0. No weights, no partial credit. Do not change that.
- Every message shown to a student from the backend is Ukrainian, as in the existing `MSG` dict in `criteria.py`. Instructor UI strings go through react-i18next with keys in BOTH `frontend/src/i18n/locales/uk/*.json` and `.../en/*.json`.
- Existing exercises must grade exactly as before unless a new option is switched on: `ignore_column_order` defaults to False; order comparison by key positions only changes verdicts for rows with equal sort keys; hidden row previews stay for lessons without a time limit.
- Commits: one or more per task, imperative subject under 72 characters, plain message, NO Co-Authored-By line, NO mention of AI, Claude or agents anywhere in the message. Do not push.
- Keep the public names importable from `grading.service` and `grading.types` (`CheckDataset`, `Execution`, `GradingTask`, `grade`, `PURPOSE_*`, `_prepare_rows`).
- Windows: files may be CRLF; preserve the line endings of the file you edit (do not reformat whole files). Python 3.12, no new dependencies.

## Review Focus

1. Ties in the sort key (two rows with the same `rating`) must pass the `order` criterion when the reference has `ORDER BY rating`, while a genuinely different order still fails (Task 1).
2. `ignore_column_order` off: `SELECT salary, name` vs reference `SELECT name, salary` still fails `complete`/`precise` (Task 1). On: it passes, and `column_names` pairs names after the permutation.
3. A timed lesson's feedback must not contain any row values, neither in `missing_rows`/`extra_rows` nor inside criterion details or hints (Tasks 1 and 2).
4. Progress percentage: a student with one perfect exercise out of twenty sees 5%, not 100% (Task 2).
5. Regrading must not change `total_attempts` and must recompute `best_score`, `best_submission`, `is_completed` from the regraded submissions; a manual score overrides the computed one everywhere a score is summed (Task 3).
6. The timer actions and the manual score are instructor-only for the course owner (or admin); another instructor and the student get 403 (Task 3).

---

### Task 1: Grading core: order by sort keys, type hint, column permutation, hidden rows, new mutants, reference warnings

**Files:**
- Modify: `backend/grading/types.py`, `backend/grading/compare.py`, `backend/grading/normalize.py`, `backend/grading/compose.py`, `backend/grading/criteria.py`, `backend/grading/service.py`, `backend/grading/runner.py`, `backend/grading/mutants.py`
- Tests: `backend/grading/test_compare.py`, `test_compose.py`, `test_criteria_eval.py` (or a new `test_criteria_order.py`), `test_mutants.py`, `test_service.py`, `test_normalize.py`

**Interfaces produced (Tasks 2-4 depend on these exact names):**
- `GradingTask.ignore_column_order: bool = False` (dataclass field in `types.py`).
- `build_task(..., ignore_column_order: bool = False)` in `runner.py`, passed through to the task.
- `grade(task, student_query, run, run_sequence=None, *, reveal_rows: bool = True)` in `service.py`; `evaluate(..., *, reveal_rows: bool = True)` in `criteria.py`.
- `compose.order_key_positions(node) -> Optional[list[int]]`.
- `compose.nondeterminism_warnings(sql: str, db_type: str) -> list[str]`.
- `compare.Diff` gains `type_only: bool = False` and `column_permutation: Optional[list[int]] = None`.
- `compare.compare(..., ordered=False, student_truncated=False, expected_truncated=False, lenient_numbers=False, key_positions: Optional[Sequence[int]] = None, ignore_column_order: bool = False)`.
- `mutants.ValidationReport.warnings: list[str]` (default empty), filled by `validate_datasets`.

- [ ] **Step 1 (problem 3): order compared by the reference's sort keys**

In `compose.py` add `order_key_positions(node)`. For the outermost `ORDER BY` of a parsed reference query (the `order` arg of the top-level `Select`, or of the top-level `Union`/`Except`/`Intersect`), map each ordering term to a 0-based index of the output column list and return the list of indices. Mapping rules, applied to the top-level select list (for a set operation use the first operand's select list):
- an integer literal `N` is the ordinal: index `N - 1` (must be within range);
- an identifier or column (table qualifier ignored, case-insensitive) that equals a select-list alias, or equals the bare column name of a select-list `Column` expression;
- any other expression whose `.sql(dialect)` with the alias removed equals a select-list expression's `.sql(dialect)` with its alias removed.
Return `None` when the select list contains `*`, when there is no `ORDER BY`, or when any term cannot be mapped (strict full-row comparison stays the fallback).

In `compare.compare` add `key_positions`: when `ordered=True` and `key_positions` is a non-empty list, the order verdict compares the two sequences of projected key tuples (`tuple(row[i] for i in key_positions)` over the normalized rows) instead of the full row sequences. Everything else (column count, truncation, multiset equality, `missing`/`extra`) is unchanged.

In `criteria.py` `Context.ordered_diff` passes `key_positions=order_key_positions(reference_node(self.task))` when the task kind is SELECT and the reference parses (for `order_matters` without `ORDER BY` this is `None`, i.e. strict). `_order` keeps its messages.

Tests (`test_compose.py`, `test_compare.py`, `test_criteria_eval.py`): ordinal `ORDER BY 2 DESC`; alias `ORDER BY total` with `SUM(amt) AS total`; bare column `ORDER BY c.rating` with `rating` in the select list; expression `ORDER BY amt * .12` matching `amt * .12` in the list; `SELECT *` gives `None`; unmappable term (`ORDER BY salary` with `salary` not selected) gives `None`; two rows with equal keys in swapped order pass `order`; rows in a different key order fail with `MSG['order']`; strict fallback still fails swapped tied rows (document this in the test name).

- [ ] **Step 2 (problem 5): hint when only the value types differ**

In `normalize.py` add `loose_value(value)`: for a normalized tagged value return a tag-free comparable form: numbers → the quantized decimal as text; strings that match `_NUMERIC_TEXT` → the same quantized decimal text as the number would give; other strings → the stripped text; temporal → the ISO text; NULL, bytes, json, nan, inf unchanged. `loose_row(row)` applies it per cell.

In `compare.compare`, when `missing` or `extra` is non-empty, set `Diff.type_only = True` if the multisets of `loose_row(...)` of student and expected rows are equal. (No change for the truncated or column-count paths.)

In `criteria.py` `_complete` and `_precise`: when `d.type_only`, use the detail `MSG['type_only']` = `'Значення збігаються, але тип стовпця інший: число записане як текст або дата як рядок. Приберіть зайве перетворення типів.'` instead of the row list. Both criteria still fail.

Tests: `('10',)` vs `(10,)` gives `type_only=True`; a real row difference gives `type_only=False`; date vs `'2000-10-03'` text gives `True`; criteria detail uses the new message.

- [ ] **Step 3 (problem 4): opt-in column order tolerance**

Add `ignore_column_order` to `GradingTask` and `build_task`. In `compare.compare` add `ignore_column_order`: when True, the column counts match and the multisets differ, look for a permutation `perm` (list where `perm[i]` is the student column index that stands for expected column `i`) such that the reordered student rows equal the expected multiset. Candidates for expected column `i` are student columns whose `Counter` of normalized values equals expected column `i`'s `Counter`; search by backtracking over expected columns with distinct student columns, verify the full-row multisets for each complete candidate; give up (treat as not equal) when there are more than 10 columns. On success return a `Diff` with `equal=True`, `kind=KIND_OK`, `column_permutation=perm`, and when `ordered=True` run the order check on the reordered student rows. When the permutation is the identity, leave `column_permutation=None`.

In `criteria.py`: `Context.diff`, `ordered_diff` and `matches_on_dataset` pass `ignore_column_order=self.task.ignore_column_order`; `diff_in_database` returns `None` when the task has `ignore_column_order` (the in-engine `EXCEPT ALL` cannot permute columns, so hidden datasets are compared in Python); `_column_names` pairs `expected[i]` with `actual[perm[i]]` when `diff.column_permutation` is set.

Tests: swapped two columns pass only with the flag; three columns with two identical value columns still resolve (verification step needed); `column_names` after permutation; ordered check after permutation; the flag does not alter a result that already matches.

- [ ] **Step 4 (problem 12): hide row previews on request**

`evaluate(..., reveal_rows=True)` stores the flag on `Context`. When `reveal_rows` is False: `_complete` detail becomes `f'Не вистачає рядків: {len(d.missing)}.'`, `_precise` becomes `f'Зайві рядки: {len(d.extra)}.'`, and `_state` lists per table `f'таблиця {table}: бракує рядків {len(d.missing)}, зайвих {len(d.extra)}'` (keep the column-count and unavailable-table texts). `grade(..., reveal_rows=...)` passes the flag to `evaluate` and, when False, puts empty lists into `feedback['missing_rows']` and `feedback['extra_rows']`. `hints` are built from the details, so they follow automatically; add a test that asserts no cell value from the dataset appears anywhere in the JSON dump of the feedback.

- [ ] **Step 5 (problem 19): more mutation classes**

In `mutants.generate_mutants` add, after the existing classes (so the existing ones keep priority under `MAX_MUTANTS`):
- `null_test`: `x IS NULL` ↔ `x IS NOT NULL` (sqlglot: `exp.Is` possibly wrapped in `exp.Not`); descriptions `'IS NULL замінено на IS NOT NULL'` / `'IS NOT NULL замінено на IS NULL'`.
- `between`: `x BETWEEN a AND b` → `x > a AND x < b`; description `'межі BETWEEN зроблено строгими'`.
- `like`: a `LIKE`/`ILIKE` pattern literal containing `%` or `_` → the same literal with those wildcard characters removed; description `'прибрано символи підстановки з шаблону LIKE'`. Skip when the stripped pattern is empty.
- `group_by`: when `GROUP BY` has two or more expressions, drop one at a time; description `f'прибрано вираз №{k} з GROUP BY'`.
- `join_condition`: for each `exp.Join` with an `on` argument, drop the condition; description `'прибрано умову з\'єднання'`.
- `not`: drop an `exp.Not` whose child is not an `exp.Is` and not an `exp.In` (those belong to the classes above/below); description `'прибрано NOT'`.
- `in_not_in`: `x IN (...)` → `x NOT IN (...)`; description `'IN замінено на NOT IN'`.
A mutant that fails to execute counts as killed (`_is_killed` already does this); keep it. Tests in `test_mutants.py`: one per class asserting the generated SQL (round-trip through sqlglot, compare normalized text), plus that `generate_mutants` of the Gruber reference `SELECT snum, SUM(amt) FROM Orders GROUP BY snum HAVING SUM(amt) > (SELECT MAX(amt) FROM Orders)` still has at most `MAX_MUTANTS` entries and the first ones are the pre-existing classes.

- [ ] **Step 6 (problems 6 and 7): warnings for the instructor**

In `compose.py` add `nondeterminism_warnings(sql, db_type) -> list[str]` (empty list when the SQL does not parse): for every `Select` that has `LIMIT`, `OFFSET` or `FETCH` but no `ORDER BY` of its own (a set operation's outer `ORDER BY` counts for its operands) add `'LIMIT без ORDER BY: набір рядків може відрізнятися між запусками.'` once; for every function call whose lower-cased name is one of `now, current_timestamp, current_date, current_time, localtimestamp, localtime, random, rand, gen_random_uuid, uuid, newid, sysdate, getdate` add `f'Функція {name}() дає різний результат при кожному запуску; еталон може не збігтися сам із собою.'` (one per distinct name; sqlglot may expose `CURRENT_TIMESTAMP` as `exp.CurrentTimestamp` etc., handle both the `exp.Anonymous`/`exp.Func` name and those node classes).

In `mutants.py` add `warnings: list[str] = field(default_factory=list)` to `ValidationReport`; `validate_datasets` fills it with `nondeterminism_warnings(reference_sql, db_type)` plus, when `len(datasets) < 2`, `'У вправи немає прихованих наборів: відповідь, що формально читає таблицю, але містить готові значення, пройде перевірку.'`. Tests for each warning and for the clean case.

- [ ] **Step 7: verify and commit**

Run `manage.py test grading --settings=config.settings_test` (was 314 tests), then the full backend suite. Commit in two or three logical commits (e.g. "feat: compare row order by the reference's sort keys", "feat: column-order tolerance and type-only hint", "feat: more mutation classes and reference warnings").

---

### Task 2: Backend wiring: required reference, column-order field, timed-lesson feedback, progress over all tasks, warnings in the dataset report

**Files:**
- Modify: `backend/courses/models.py`, `backend/courses/serializers.py`, `backend/courses/views.py`, `backend/assignments/models.py`, `backend/assignments/serializers.py`, `backend/submissions/views.py`
- Create: `backend/courses/migrations/0016_lessonexercise_ignore_column_order.py`, `backend/assignments/migrations/000N_assignment_ignore_column_order.py` (use `makemigrations`), `backend/submissions/progress.py`
- Tests: `backend/courses/test_criteria_api.py` (extend), `backend/submissions/test_grading_flow.py` (extend), new `backend/submissions/test_progress.py`

**Interfaces consumed from Task 1:** `build_task(..., ignore_column_order=...)`, `grade(..., reveal_rows=...)`, `ValidationReport.warnings`.

**Interfaces produced (Task 4 depends on these):**
- `LessonExercise.ignore_column_order` and `Assignment.ignore_column_order` (boolean, default False) readable and writable through the existing exercise and assignment serializers; copied by course duplication.
- Progress payload shape unchanged (`course_id`, `course_title`, `total_assignments`, `completed_assignments`, `total_score`, `max_possible_score`, `completion_rate`, `percentage_score`) but computed over all published tasks.
- `validate-exercises` entries gain `"warnings": [str, ...]`.
- Exercise validation error shape: `{"exercises": [{"expected_query": ["Потрібен еталонний запит: без нього відповідь не перевіряється."]}, ...]}` (standard DRF nested errors); assignment: `{"expected_query": ["..."]}`.

- [ ] **Step 1 (problem 2): the reference query is required**

`LessonExerciseSerializer.validate(attrs)`: when the payload contains `expected_query` and it is empty after `strip()`, and the payload's `expected_result` is not a dict, raise `serializers.ValidationError({'expected_query': 'Потрібен еталонний запит: без нього відповідь не перевіряється.'})`. Same rule in the assignment create/update serializer. Payloads that do not contain the key (partial updates) are not affected. Tests: creating a lesson with an exercise without `expected_query` returns 400 with that key; with a legacy `expected_result` dict it is accepted; assignments likewise.

- [ ] **Step 2 (problem 4): `ignore_column_order` field**

Add `ignore_column_order = models.BooleanField(default=False)` to `LessonExercise` and `Assignment`; migrations via `makemigrations courses assignments`. Expose in `LessonExerciseSerializer` and the assignment serializers (writable). `criteria_task()` and `build_task` calls in `submissions/views.py` pass it. Course duplication (`CourseViewSet.duplicate`) copies it, and also copies `criteria` (it currently drops `criteria`; fix that in the same place). Tests: round trip through the lesson API; a submission flow test with the SQLite fake-free path from `test_grading_flow.py` where the student swaps two columns and passes only when the flag is on; duplication keeps `criteria` and the flag.

- [ ] **Step 3 (problem 12): timed lessons hide row previews**

In `SubmissionViewSet.create` pass `reveal_rows=not (lesson is not None and bool(lesson.time_limit_seconds))` to `grade_submission`. Test: a lesson with `time_limit_seconds=600` and a wrong answer: `feedback['missing_rows'] == []`, no criterion detail contains a cell value, while the same submission on an untimed lesson does contain the rows.

- [ ] **Step 4 (problem 15): progress over all published tasks**

Create `backend/submissions/progress.py` with `course_progress(student, courses) -> list[dict]`: for each course (in the given order) the tasks are the published assignments plus the exercises of published lessons whose `lesson_type` is `practice` or `mixed`; `total_assignments` = number of tasks, `max_possible_score` = sum of their `max_score`, `completed_assignments` = number of the student's `UserResult` rows with `is_completed=True` for those tasks, `total_score` = sum of the student's effective score (`manual_score` when not null, else `best_score`; Task 3 adds `manual_score`, so in this task read it with `getattr(result, 'manual_score', None)` and leave a one-line comment) over those tasks; `completion_rate` and `percentage_score` rounded to 2 places as today, 0 when the denominator is 0. Use at most a handful of queries for all courses together (aggregate with `values()`/`annotate`, no per-course loops hitting the database per task). `my_progress` uses the student's active enrollments (`Enrollment.status == 'active'`), optional `?course=` filter kept; `student_progress` uses the student's active enrollments restricted to courses the requesting instructor owns. Keep the response keys. Tests (`test_progress.py`): 20 exercises, one perfect → `percentage_score == 5.0`, `completion_rate == 5.0`; unpublished lesson excluded; a course with an enrollment but no results appears with zeros; another instructor's course not in `student_progress`.

- [ ] **Step 5 (problems 6 and 7): warnings in the dataset report**

`LessonViewSet.validate_exercises` adds `'warnings': result.warnings` to each entry. Test: an exercise with no `check_datasets` gets the "немає прихованих наборів" warning; one with `LIMIT` and no `ORDER BY` gets the LIMIT warning (use the SQLite path; `make_runner` works without Docker for `sqlite`).

- [ ] **Step 6: verify and commit**

Full backend suite green. Commits per step or grouped sensibly.

---

### Task 3: Instructor tools: timer control, regrading, manual score

**Files:**
- Modify: `backend/submissions/models.py`, `backend/submissions/serializers.py`, `backend/submissions/views.py`, `backend/submissions/timing.py`, `backend/courses/views.py`, `backend/assignments/views.py`, `backend/config/urls.py` (only if a route is needed)
- Create: `backend/submissions/migrations/0010_manual_score_and_timer_extension.py` (via `makemigrations`), `backend/submissions/regrade.py`
- Tests: `backend/submissions/test_lesson_timer.py` (extend), new `backend/submissions/test_regrade.py`, new `backend/submissions/test_manual_score.py`

**Interfaces produced (Task 4 depends on these exact routes and payloads):**
- `UserResult.extra_seconds` (PositiveIntegerField, default 0), `manual_score` (Decimal 5,2 nullable), `manual_comment` (Text, blank), `manual_set_by` (FK user, SET_NULL, nullable, related_name `+`), `manual_set_at` (nullable datetime); property `effective_score` (= `manual_score` if not None else `best_score`).
- `GET /api/courses/{course}/timers/?student=<uuid>` (course owner or admin): list of `{lesson_id, lesson_title, time_limit_seconds, started_at, deadline, remaining_seconds, extra_seconds}` for every published lesson with a time limit, in lesson order. `started_at`/`deadline`/`remaining_seconds` are null when the student has not started.
- `POST /api/courses/{course}/lessons/{lesson}/timer/` body `{"student": "<uuid>", "action": "reset"}` or `{"student": "<uuid>", "action": "extend", "minutes": 10}` (1 ≤ minutes ≤ 180); 400 when the lesson has no time limit or the action is unknown; 403 for students and for instructors who do not own the course; returns the same object as one `timers` entry.
- `POST /api/courses/{course}/lessons/{lesson}/regrade/` body optional `{"exercise_id": "<uuid>"}`; `POST /api/courses/{course}/assignments/{assignment}/regrade/` with no body. Owner or admin only. Response `{"submissions": n, "changed": m, "truncated": bool}`.
- `PATCH /api/results/{id}/` body `{"manual_score": 85 | null, "manual_comment": "..."}` (owner of the result's course or admin; 403 otherwise; `manual_score` must be between 0 and the task's `max_score`); response is the serialized result.
- `GET /api/results/?course=<id>&student=<id>` and `GET /api/results/?lesson=<id>` filters (instructors may pass `student`; students always see only their own). `UserResultSerializer` gains `exercise`, `lesson`, `exercise_title`, `lesson_title`, `max_score`, `extra_seconds`, `manual_score`, `manual_comment`, `manual_set_at`, `effective_score`.

- [ ] **Step 1 (problem 13): timer extension and reset**

Model field `extra_seconds`. `timing.py`: `timing_for` and `time_is_up` use `time_limit_seconds + result.extra_seconds`; `timing_for` returns `extra_seconds` too. `LessonViewSet.timer` action (`url_path='timer'`): `reset` sets `started_at=None` and `extra_seconds=0` on the lesson-level row if it exists (no row: no-op, still 200); `extend` adds `minutes * 60` to `extra_seconds` (creating the lesson-level row with `started_at=None` if missing, so the extension applies when the student starts). `CourseViewSet.timers` action (`url_path='timers'`, GET). Permission helper: course owner or `role == 'admin'`/superuser. Tests: reset clears both fields; extend moves the deadline by the minutes and `time_is_up` honours it; student 403; foreign instructor 403; lesson without limit 400.

- [ ] **Step 2 (problem 14, part 1): regrade**

Extract the task-building part of `SubmissionViewSet.create` into `submissions/regrade.py`: `grading_setup_for_exercise(exercise, lesson) -> (task, runner, sequence_runner)` and `grading_setup_for_assignment(assignment)`, both using `build_task`, `make_runner`, `make_sequence_runner` exactly as `create` does today (keep the `time_limit` defaults 600 for lessons and 30 for assignments, pass `ignore_column_order`), with `user_id`/`submission_id`/`dataset_id` attribution optional. `create` must call these helpers so the two paths cannot drift. Add `regrade_submissions(submissions_qs, setup, *, reveal_rows, max_count=300, budget_seconds=60) -> dict`: for each submission (oldest first) regrade with `grade_submission`, store `score`, `is_correct`, `feedback` (json_safe), `graded_at`, `status`/`error_message`/`result` as `create` does; count `changed` when `score` or `is_correct` differ; stop at `max_count` or when the budget is exhausted and report `truncated`. Afterwards recompute every touched `UserResult` from its submissions: `best_score` = max score, `best_submission` = the earliest submission with that score, `is_completed` = any `is_correct`, `first_completed_at` = earliest correct submission's `submitted_at`; `total_attempts`, `manual_*` and `extra_seconds` untouched. Wrap each submission's save in `transaction.atomic()`. Add the two `regrade` actions. Tests (`test_regrade.py`, SQLite flow like `test_grading_flow.py`): after changing the reference, a previously wrong answer becomes correct and vice versa; `total_attempts` unchanged; `best_submission` updated; `truncated` with `max_count=1`; permissions.

- [ ] **Step 3 (problem 14, part 2): manual score**

Model fields `manual_score`, `manual_comment`, `manual_set_by`, `manual_set_at`, property `effective_score`. `UserResultViewSet` becomes a `ModelViewSet` with `http_method_names = ['get', 'patch', 'head', 'options']`; `partial_update` only accepts `manual_score` and `manual_comment` through a dedicated `ManualScoreSerializer`, validates the range against the task's `max_score` (exercise or assignment), sets `manual_set_by`/`manual_set_at` (clears them when `manual_score` is null and comment empty). Permission: owner of the course the result belongs to, or admin. `UserResultSerializer` gains the fields listed above (`max_score` from the exercise or assignment; titles). `get_queryset`: add `student` (instructors only) and `lesson` filters. `progress.py` from Task 2 already reads `manual_score`; remove the `getattr` fallback there and use the property. Tests (`test_manual_score.py`): owner PATCH stores and returns `effective_score`; student 403; foreign instructor 403; value above `max_score` 400; null clears; progress uses the manual score.

- [ ] **Step 4: verify and commit**

Full backend suite green. Commit per step.

---

### Task 4: Frontend: required reference, column-order switch, warnings, timer tools, regrade and manual score

**Files:**
- Modify: `frontend/src/lib/schemas.ts`, `frontend/src/api/lessons.ts`, `frontend/src/api/assignments.ts`, `frontend/src/api/submissions.ts`, `frontend/src/api/courses.ts`, `frontend/src/types/index.ts`, `frontend/src/hooks/queries/useLessons.ts`, `useSubmissions.ts`, `useCourses.ts`, `frontend/src/pages/instructor/LessonFormPage.tsx`, `StudentsPage.tsx` (course students), `CourseManagePage.tsx`, `frontend/src/pages/lessons/LessonPage.tsx`, the assignment form if one exists, `frontend/src/i18n/locales/{uk,en}/instructor.json` and `lessons.json`
- Create: `frontend/src/components/instructor/StudentTimersDialog.tsx`, `frontend/src/components/instructor/StudentResultsDialog.tsx` (names may follow the existing component conventions)

**Interfaces consumed:** the routes and payloads listed under Tasks 2 and 3.

- [ ] **Step 1 (problem 2):** zod: `expected_query: z.string().min(1, 'required')` for exercises (the message comes from i18n at render time as the other field errors do; follow the existing pattern in `schemas.ts`). Show the field error under the expected-query editor in `LessonFormPage`. Same for the assignment form if the app has one (check `src/pages`). Also surface the backend's nested error for `exercises[i].expected_query` when it comes back (the existing `getApiErrorMessage` path is enough if it renders the first nested message; verify).

- [ ] **Step 2 (problem 4):** `ignore_column_order` in the `LessonExercise`/`Assignment` types, form defaults, payload mapping, and a `Switch` labelled (uk) "Порядок стовпців не важливий" with the hint "Відповідь зараховується, якщо ті самі стовпці йдуть в іншому порядку." (en: "Column order does not matter" / "The answer is accepted when the same columns come in a different order.") placed next to the existing `order_matters` control.

- [ ] **Step 3 (problems 6, 7):** `ExerciseValidation` type gains `warnings: string[]`; the dataset-check report in `LessonFormPage` renders them as a list with a warning icon above the surviving mutants. Additionally, in the exercise editor show a muted hint under "Hidden check datasets" when the list is empty: (uk) "Без прихованих наборів відповідь, підігнану під видимі дані, не буде відрізнено від правильної." (en: "Without hidden datasets an answer fitted to the visible data cannot be told from a correct one.")

- [ ] **Step 4 (problem 13):** On the course students page, a per-student action "Час контрольних" opening `StudentTimersDialog`: fetches `GET /courses/{id}/timers/?student=`, lists each timed lesson with started/deadline/remaining (format with the existing date helpers) and extra minutes, buttons "Скинути час" (confirm dialog) and "+ хвилин" with a number input (default 10, 1–180) calling `POST /courses/{c}/lessons/{l}/timer/`. Hide the action when the course has no timed lessons (the list is empty). Toasts on success and error.

- [ ] **Step 5 (problem 14):** `StudentResultsDialog` on the same page: `GET /results/?course=&student=` grouped by lesson (and assignments), one row per exercise: title, best score / max, attempts, completed badge, manual score input and comment, "Зберегти" calling `PATCH /results/{id}/`, "Скинути" sending `manual_score: null, manual_comment: ''`. On `CourseManagePage`, for every lesson with exercises a "Перевірити заново" action (confirm dialog explaining that all answers of the lesson will be regraded with the current reference and criteria) calling `POST /courses/{c}/lessons/{l}/regrade/` and showing a toast with `submissions`/`changed` and a note when `truncated`. On the student `LessonPage`, fetch `GET /results/?lesson=<id>` once and, for an exercise whose result has `manual_score` not null, show a small card "Оцінка викладача: X / max" with the comment above the submission history.

- [ ] **Step 6:** i18n keys in uk and en for everything above (plural keys where counts appear: `_one/_few/_many/_other` for uk, `_one/_other` for en). `npm run build` passes; `npx tsc -b --noEmit` shows no new errors; `npm run lint` shows no new errors. Commit per step or grouped.

---

### Task 5: Documentation

**Files:**
- Modify: `GRADING_ALGORITHM.md`, `PROJECT_DOCUMENTATION.md` (API list in section 12 and the grading summary in section 9)

- [ ] **Step 1:** Part I of `GRADING_ALGORITHM.md`: section 5 (order compared by the sort keys of the reference; ties interchangeable; strict fallback when the key is not in the output); section 3.1 gets the "порядок стовпців не важливий" option; section 10.1 table row for column names mentions the permutation; section 10.4 adds the type-only hint; section 13 lists the new mutation classes and the warnings (LIMIT without ORDER BY, volatile functions, no hidden datasets); section 11 gets "ручний бал викладача" and "перевірити заново"; section 12 gets "скинути час" and "додати хвилини"; section 15 notes that timed lessons show counts instead of rows. Section 16 test counts: take the real numbers from `manage.py test --settings=config.settings_test` and `manage.py test grading`.
- [ ] **Step 2:** Part II: mark problems 2, 3, 4, 5, 6, 7, 12, 13, 14, 15, 19 as "(виправлено 30.10.2026)" in the heading, keep the original description, add one sentence saying what was done (as entry 1 does). Update "Рекомендований порядок" to list only the remaining items (8, 9, 10, 11, 16, 17, 18, 20, 21).
- [ ] **Step 3:** `PROJECT_DOCUMENTATION.md`: add the new endpoints (timers, timer, regrade, results PATCH, filters) to section 12; mention the new fields in section 11 if the ER list enumerates fields. Keep the file's language (Russian) and line endings (CRLF).
- [ ] **Step 4:** Commit: "docs: describe the grading fixes of 2026-10-30".

---

### Task 6: Bounded row fetch in the sandbox executors

**Files:**
- Modify: `backend/sandbox/executors/postgresql.py`, `backend/sandbox/executors/mysql.py`, `backend/sandbox/executors/sqlite.py`
- Tests: `backend/sandbox/tests.py` (or a new `backend/sandbox/test_executor_limits.py`)

**Why:** the executors call `cursor.fetchall()` and only then slice to `MAX_RESULT_ROWS` (1000), so a query that returns millions of rows (a cross join, or the `join_condition` mutant of Task 1 on a large dataset) is materialised in the backend process before the cap applies. The cap must bound peak memory, not only the returned list.

- [ ] **Step 1:** In each of the three executors replace the `fetchall()` + slice with `cursor.fetchmany(MAX_RESULT_ROWS + 1)`; `truncated = len(rows) > MAX_RESULT_ROWS`; keep the returned rows at most `MAX_RESULT_ROWS` and keep everything else (column names, affected rows, timing, error handling) unchanged. For psycopg, make sure the cursor is a client-side cursor as today (no server-side cursor needed). Only the result-set branch changes; the `fetchall()` calls used for listing tables and sequences during reset stay.
- [ ] **Step 2:** Test with the in-process SQLite executor: a query producing 2500 rows (`WITH RECURSIVE n(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM n WHERE x < 2500) SELECT x FROM n`) returns exactly 1000 rows with `truncated=True`; a query producing 1000 rows returns 1000 with `truncated=False`; 1001 rows gives `truncated=True`. PostgreSQL and MariaDB cannot be exercised locally (no Docker); state that in the report.
- [ ] **Step 3:** Run `manage.py test sandbox --settings=config.settings_test` and the full suite; commit as "fix: cap sandbox result fetch at the row limit".

---

### Task 7: Server-side result streaming for PostgreSQL and MariaDB

**Files:**
- Modify: `backend/sandbox/executors/postgresql.py`, `backend/sandbox/executors/mysql.py`
- Tests: `backend/sandbox/test_grading_engines.py` (integration, runs only with `SANDBOX_INTEGRATION=1` against real sandboxes), `backend/sandbox/test_executor_limits.py` (unit, with the driver cursor faked)

**Why:** after Task 6 the executors fetch at most 1001 rows, but psycopg2 and PyMySQL default cursors still transfer and buffer the whole result set in the backend process during `execute()`. A cross join on a large dataset can exhaust the backend container's memory before the cap applies. The sandbox engines must stream so that only `MAX_RESULT_ROWS + 1` rows ever reach the backend.

- [ ] **Step 1 (PostgreSQL):** classify the statement by its first keyword after leading whitespace and comments (`SELECT`, `WITH`, `VALUES`, `TABLE` → row-returning query). For those use a named cursor declared `WITH HOLD` (`self._connection.cursor(name='sandbox_fetch', withhold=True)`, `itersize = MAX_RESULT_ROWS + 1`) because the connection runs in autocommit; fetch with `fetchmany(MAX_RESULT_ROWS + 1)`, read `description` after the fetch (named cursors populate it on the first fetch), then close the cursor (which issues `CLOSE`). Everything else (DML, DDL, EXPLAIN, SHOW, SET, `... RETURNING`) keeps the regular cursor path from Task 6. `statement_timeout` handling, `QueryCanceled`/`SyntaxError` mapping, timing and `affected_rows` stay as they are. If declaring the cursor fails with a syntax-class error for a statement that was classified as a query (e.g. a `SELECT ... INTO`), fall back to the regular cursor once.
- [ ] **Step 2 (MariaDB):** use `pymysql.cursors.SSCursor` for the same statement class; `fetchmany(MAX_RESULT_ROWS + 1)`; when the result is truncated, do not let `close()` drain the remainder: close the connection (`self._connection.close()` sends QUIT, the server discards the rest) and reconnect with `self.connect()` before returning. When not truncated, close the cursor normally. Keep the regular cursor for all other statements.
- [ ] **Step 3 (tests):** unit tests in `test_executor_limits.py` that fake the driver cursor objects (a small stub class) to assert: a query-class statement opens the streaming cursor, a non-query statement does not, truncation triggers the reconnect on MariaDB and the cursor close on PostgreSQL. Integration tests in `test_grading_engines.py` (guarded like the existing ones by `SANDBOX_INTEGRATION`) that run `WITH RECURSIVE` / `seq_1_to_2500` style queries producing 2500 rows on PostgreSQL and MariaDB and assert 1000 rows with `truncated=True`, plus one DML statement and one `SELECT` with an empty result (description still present, `columns` filled) on each engine.
- [ ] **Step 4:** full suite green locally (the integration classes skip), commit "fix: stream sandbox results instead of buffering them". The controller runs the integration tests on the server after deployment.

---

### Task 8: Row cap inside user transactions and for multi-statement strings

**Files:**
- Modify: `backend/sandbox/executors/postgresql.py`, `backend/sandbox/executors/mysql.py`
- Tests: `backend/sandbox/test_executor_limits.py`, `backend/sandbox/test_grading_engines.py`

**Why:** after Task 7 two paths still buffer a whole result in the backend process: a row query issued inside a transaction the user opened in a persistent playground session (`BEGIN; SELECT <huge>`), and on PostgreSQL a multi-statement string whose last statement returns rows (`SELECT 1; SELECT <huge>`). Both are playground-only (grading rejects multiple statements and never opens transactions), but the cap must hold everywhere.

- [ ] **Step 1 (PostgreSQL, inside a user transaction):** when the connection is `INTRANS` and the statement is a single row query, stream inside the user's transaction without touching it: `SAVEPOINT sandbox_cursor`; `DECLARE "<unique name>" NO SCROLL CURSOR FOR <query>` executed as plain SQL through a regular cursor; `FETCH FORWARD <MAX_RESULT_ROWS + 1> FROM "<name>"` (the FETCH's `cursor.description` gives the columns, its rows are the result; `truncated = len(rows) > MAX_RESULT_ROWS`); `CLOSE "<name>"`; `RELEASE SAVEPOINT sandbox_cursor`. If the DECLARE is rejected (the statement is not declarable, e.g. `SELECT ... INTO` or a data-modifying `WITH`), `ROLLBACK TO SAVEPOINT sandbox_cursor` and run the statement once through the regular path, so the user's transaction survives. No commit, no rollback, no autocommit change on this path. `INERROR` state keeps the regular path (every statement fails there anyway).
- [ ] **Step 2 (MariaDB, inside a user transaction):** keep the buffered cursor but bound it server-side: `SET SESSION sql_select_limit = <MAX_RESULT_ROWS + 1>` before the row query and `SET SESSION sql_select_limit = DEFAULT` after it (also on the error path), so at most 1001 rows are ever sent; `truncated` as usual. Do not reconnect inside a transaction.
- [ ] **Step 3 (PostgreSQL multi-statement strings):** split the string into statements with the same tokenizer the validator uses (slice the original text at top-level `;` tokens so literals, comments and dollar-quoted strings are safe; drop empty trailing pieces). When the connection is idle: open one explicit transaction (autocommit off), execute every statement but the last through a regular cursor, stream the last one with the Task 7 named-cursor path when it is a row query (else run it plainly), then commit; any error rolls the whole transaction back and maps to the usual exceptions, so the script stays atomic exactly as psycopg2's single multi-statement execute was. The returned `QueryResult` is the last statement's, as today. When the connection is `INTRANS`, execute the pieces one by one inside the user's transaction, applying Step 1 to the last piece. MariaDB needs nothing here: the connection does not enable `CLIENT.MULTI_STATEMENTS`, so such strings already fail.
- [ ] **Step 4 (tests):** unit tests with faked driver objects for each new path (declare-in-transaction, savepoint fallback, `sql_select_limit` set and reset including on error, statement splitting on literals/comments/dollar quotes, atomic rollback of a failing script). Integration tests on both engines (guarded like the existing ones): `BEGIN; <2500-row SELECT>` returns 1000 rows truncated and the transaction is still open and usable (a following `ROLLBACK` works); `BEGIN; UPDATE; SELECT ... INTO`-style rejected DECLARE falls back and the transaction survives; a PostgreSQL script `CREATE TEMP TABLE t AS ...; INSERT ...; SELECT * FROM t` returns the last result; a failing script leaves no trace of its earlier statements; a script whose last statement is a 2500-row SELECT is capped.
- [ ] **Step 5:** sandbox and full suites green locally, integration classes green against the local sandboxes (`docker compose -f docker-compose.yml -f docker-compose.dev-ports.yml up -d sandbox-postgres sandbox-mariadb`, ports 55432/53306, or temporary containers as in Task 7), commit "fix: cap sandbox results inside transactions and scripts".
