import type { CriteriaSummary, ExerciseCriteria } from '@/types';
import apiClient from './client';
import type { PaginatedResponse, Submission } from '@/types';

export type LessonType = 'theory' | 'practice' | 'mixed';

export interface CheckDataset {
  name: string;
  seed_sql: string;
  schema_sql?: string;
  targets?: string;
}

export interface LessonExercise {
  id?: string;
  order: number;
  title: string;
  description?: string;
  initial_code?: string;
  expected_query?: string;
  expected_result?: unknown;
  check_datasets?: CheckDataset[];
  required_keywords?: string[];
  forbidden_keywords?: string[];
  order_matters?: boolean;
  max_score: number;
  hints?: string[];
  criteria?: ExerciseCriteria;
  criteria_summary?: CriteriaSummary;
  dataset?: {
    id: string;
    name: string;
    description: string;
    schema_sql: string;
    seed_sql: string;
  } | null;
  dataset_id?: string;
}

export interface Lesson {
  id: string;
  course: string;
  course_title?: string;
  database_type?: string;
  title: string;
  description: string;
  lesson_type: LessonType;
  order: number;
  module: string;
  theory_content?: string;
  time_limit_seconds: number | null;
  max_attempts?: number;
  exercises: LessonExercise[];
  is_published: boolean;
  user_completed?: boolean;
  user_best_score?: number;
  created_at: string;
  updated_at?: string;
}

export interface CreateLessonData {
  title: string;
  description?: string;
  lesson_type: string;
  order?: number;
  theory_content?: string;
  time_limit_seconds?: number | null;
  max_attempts?: number;
  exercises?: LessonExercise[];
  module_id: string;
  is_published?: boolean;
}

export type UpdateLessonData = Partial<CreateLessonData>;

export interface SurvivingMutant {
  kind: string;
  description: string;
  sql: string;
}

export interface ExerciseValidation {
  exercise_id: string;
  title: string;
  skipped?: string;
  error?: string;
  datasets?: string[];
  mutants_total?: number;
  checked?: number;
  truncated?: boolean;
  killed?: number;
  surviving?: SurvivingMutant[];
  reference_empty_on?: string[];
  reference_errors?: Record<string, string>;
}

export interface LessonValidation {
  lesson_id: string;
  exercises: ExerciseValidation[];
}

export interface LessonTiming {
  started_at: string | null;
  time_limit_seconds: number | null;
  deadline: string | null;
  remaining_seconds: number | null;
}

const lessonsApi = {
  list: async (courseId: string) => {
    const response = await apiClient.get<PaginatedResponse<Lesson>>(
      `/courses/${courseId}/lessons/`
    );
    return response.data;
  },

  get: async (courseId: string, id: string) => {
    const response = await apiClient.get<Lesson>(
      `/courses/${courseId}/lessons/${id}/`
    );
    return response.data;
  },

  create: async (courseId: string, data: CreateLessonData) => {
    const response = await apiClient.post<Lesson>(
      `/courses/${courseId}/lessons/`,
      data
    );
    return response.data;
  },

  update: async (courseId: string, id: string, data: UpdateLessonData) => {
    const response = await apiClient.patch<Lesson>(
      `/courses/${courseId}/lessons/${id}/`,
      data
    );
    return response.data;
  },

  delete: async (courseId: string, id: string) => {
    await apiClient.delete(`/courses/${courseId}/lessons/${id}/`);
  },

  reorder: async (courseId: string, lessonIds: string[]) => {
    const response = await apiClient.post(
      `/courses/${courseId}/lessons/reorder/`,
      { lesson_ids: lessonIds }
    );
    return response.data;
  },

  start: async (courseId: string, lessonId: string) => {
    const response = await apiClient.post<LessonTiming>(
      `/courses/${courseId}/lessons/${lessonId}/start/`
    );
    return response.data;
  },

  validateExercises: async (courseId: string, lessonId: string) => {
    const response = await apiClient.post<LessonValidation>(
      `/courses/${courseId}/lessons/${lessonId}/validate-exercises/`
    );
    return response.data;
  },

  // Submit practice
  submit: async (courseId: string, lessonId: string, query: string, exerciseId: string) => {
    const response = await apiClient.post<Submission>(
      `/courses/${courseId}/lessons/${lessonId}/submissions/`,
      { query, exercise_id: exerciseId }
    );
    return response.data;
  },

  getMySubmissions: async (courseId: string, lessonId: string) => {
    const response = await apiClient.get<Submission[]>(
      `/courses/${courseId}/lessons/${lessonId}/submissions/my/`
    );
    return response.data;
  },
};

export default lessonsApi;
