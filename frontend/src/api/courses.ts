import apiClient from './client';
import type { Course, Dataset, Enrollment, PaginatedResponse } from '@/types';

export interface CreateCourseData {
  title: string;
  description: string;
  database_type: string;
  enrollment_key?: string;
  max_students?: number;
  start_date?: string;
  end_date?: string;
}

export interface UpdateCourseData extends Partial<CreateCourseData> {
  is_published?: boolean;
}

export interface CreateDatasetData {
  name: string;
  description?: string;
  schema_sql: string;
  seed_sql?: string;
  is_default?: boolean;
}

const coursesApi = {
  list: async (params?: { search?: string; is_published?: boolean }) => {
    const response = await apiClient.get<PaginatedResponse<Course>>('/courses/', { params });
    return response.data;
  },

  get: async (id: string) => {
    const response = await apiClient.get<Course>(`/courses/${id}/`);
    return response.data;
  },

  create: async (data: CreateCourseData) => {
    const response = await apiClient.post<Course>('/courses/', data);
    return response.data;
  },

  update: async (id: string, data: UpdateCourseData) => {
    const response = await apiClient.patch<Course>(`/courses/${id}/`, data);
    return response.data;
  },

  delete: async (id: string) => {
    await apiClient.delete(`/courses/${id}/`);
  },

  enroll: async (id: string, enrollmentKey?: string) => {
    const response = await apiClient.post<Enrollment>(`/courses/${id}/enroll/`, {
      enrollment_key: enrollmentKey,
    });
    return response.data;
  },

  unenroll: async (id: string) => {
    await apiClient.post(`/courses/${id}/unenroll/`);
  },

  getEnrollments: async (id: string) => {
    const response = await apiClient.get<Enrollment[]>(`/courses/${id}/students/`);
    return response.data;
  },

  getMyEnrollments: async () => {
    const response = await apiClient.get<PaginatedResponse<Enrollment>>('/enrollments/');
    return response.data;
  },

  // Datasets
  getDatasets: async (courseId: string) => {
    const response = await apiClient.get<Dataset[]>(`/courses/${courseId}/datasets/`);
    return response.data;
  },

  createDataset: async (courseId: string, data: CreateDatasetData) => {
    const response = await apiClient.post<Dataset>(`/courses/${courseId}/datasets/`, data);
    return response.data;
  },

  updateDataset: async (courseId: string, datasetId: string, data: Partial<CreateDatasetData>) => {
    const response = await apiClient.patch<Dataset>(
      `/courses/${courseId}/datasets/${datasetId}/`,
      data
    );
    return response.data;
  },

  deleteDataset: async (courseId: string, datasetId: string) => {
    await apiClient.delete(`/courses/${courseId}/datasets/${datasetId}/`);
  },

  duplicate: async (courseId: string, title?: string) => {
    const response = await apiClient.post<Course>(`/courses/${courseId}/duplicate/`, {
      title,
    });
    return response.data;
  },
};

export default coursesApi;
