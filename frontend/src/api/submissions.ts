import apiClient from './client';
import type { Submission, UserResult, PaginatedResponse, CourseProgress } from '@/types';

export interface SubmitQueryData {
  query: string;
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

  // Progress
  getMyProgress: async () => {
    const response = await apiClient.get<CourseProgress[]>('/results/my_progress/');
    return response.data;
  },

  getCourseProgress: async (courseId: string) => {
    const response = await apiClient.get<CourseProgress>(`/results/my_progress/?course=${courseId}`);
    return response.data;
  },
};

export default submissionsApi;
