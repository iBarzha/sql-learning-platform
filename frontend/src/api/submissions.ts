import apiClient from './client';
import type {
  Submission,
  UserResult,
  PaginatedResponse,
  CourseProgress,
  StudentResult,
  ManualScoreData,
} from '@/types';

export interface SubmitQueryData {
  query: string;
}

export function resultStudentId(result: StudentResult): string {
  return typeof result.student === 'string' ? result.student : result.student.id;
}

const submissionsApi = {
  submit: async (courseId: string, assignmentId: string, data: SubmitQueryData) => {
    const response = await apiClient.post<Submission>(
      `/courses/${courseId}/assignments/${assignmentId}/submissions/`,
      data
    );
    return response.data;
  },

  list: async (courseId: string, assignmentId: string) => {
    const response = await apiClient.get<PaginatedResponse<Submission>>(
      `/courses/${courseId}/assignments/${assignmentId}/submissions/`
    );
    return response.data;
  },

  get: async (courseId: string, assignmentId: string, id: string) => {
    const response = await apiClient.get<Submission>(
      `/courses/${courseId}/assignments/${assignmentId}/submissions/${id}/`
    );
    return response.data;
  },

  getMySubmissions: async (courseId: string, assignmentId: string) => {
    const response = await apiClient.get<Submission[]>(
      `/courses/${courseId}/assignments/${assignmentId}/submissions/my/`
    );
    return response.data;
  },

  // User Results
  getMyResults: async (courseId: string) => {
    const response = await apiClient.get<UserResult[]>(`/courses/${courseId}/results/my/`);
    return response.data;
  },

  getAllResults: async (courseId: string) => {
    const response = await apiClient.get<PaginatedResponse<UserResult>>(
      `/courses/${courseId}/results/`
    );
    return response.data;
  },

  // Per-task results: an instructor filters by course and student, a student by lesson.
  // The list may be paginated; every page is fetched so no task is left out.
  listResults: async (params: { course?: string; student?: string; lesson?: string }) => {
    const results: StudentResult[] = [];
    for (let page = 1; ; page++) {
      const response = await apiClient.get<StudentResult[] | PaginatedResponse<StudentResult>>(
        '/results/',
        { params: { ...params, page } }
      );
      const data = response.data;
      if (Array.isArray(data)) return data;
      results.push(...data.results);
      if (!data.next) return results;
    }
  },

  setManualScore: async (resultId: string, data: ManualScoreData) => {
    const response = await apiClient.patch<StudentResult>(`/results/${resultId}/`, data);
    return response.data;
  },

  // Progress
  getMyProgress: async () => {
    const response = await apiClient.get<CourseProgress[]>('/results/my_progress/');
    return response.data;
  },

  getCourseProgress: async (courseId: string) => {
    const response = await apiClient.get<CourseProgress>(`/results/my_progress/?course=${courseId}`);
    return response.data;
  },

  getStudentProgress: async (studentId: string) => {
    const response = await apiClient.get<CourseProgress[]>(
      `/results/student_progress/?student=${studentId}`
    );
    return response.data;
  },
};

export default submissionsApi;
