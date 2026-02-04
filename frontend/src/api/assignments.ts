import apiClient from './client';
import type { Assignment, PaginatedResponse } from '@/types';

export interface CreateAssignmentData {
  title: string;
  description: string;
  instructions?: string;
  dataset?: string;
  query_type: string;
  difficulty: string;
  expected_query?: string;
  expected_result?: unknown;
  required_keywords?: string[];
  forbidden_keywords?: string[];
  order_matters?: boolean;
  partial_match?: boolean;
  max_score?: number;
  time_limit_seconds?: number;
  max_attempts?: number;
  hints?: string[];
  due_date?: string;
  is_published?: boolean;
  order?: number;
}

export type UpdateAssignmentData = Partial<CreateAssignmentData>;

const assignmentsApi = {
  list: async (courseId: string, params?: { is_published?: boolean }) => {
    const response = await apiClient.get<PaginatedResponse<Assignment>>(
      `/courses/${courseId}/assignments/`,
      { params }
    );
    return response.data;
  },

  get: async (courseId: string, id: string) => {
    const response = await apiClient.get<Assignment>(`/courses/${courseId}/assignments/${id}/`);
    return response.data;
  },

  create: async (courseId: string, data: CreateAssignmentData) => {
    const response = await apiClient.post<Assignment>(
      `/courses/${courseId}/assignments/`,
      data
    );
    return response.data;
  },

  update: async (courseId: string, id: string, data: UpdateAssignmentData) => {
    const response = await apiClient.patch<Assignment>(
      `/courses/${courseId}/assignments/${id}/`,
      data
    );
    return response.data;
  },

  delete: async (courseId: string, id: string) => {
    await apiClient.delete(`/courses/${courseId}/assignments/${id}/`);
  },

  reorder: async (courseId: string, assignmentIds: string[]) => {
    const response = await apiClient.post(`/courses/${courseId}/assignments/reorder/`, {
      assignment_ids: assignmentIds,
    });
    return response.data;
  },
};

export default assignmentsApi;
