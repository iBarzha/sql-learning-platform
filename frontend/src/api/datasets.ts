import apiClient from './client';

export interface Dataset {
  id: string;
  name: string;
  description: string;
  database_type: string;
  schema_sql: string;
  seed_sql: string;
  quick_start_queries?: Record<string, string>;
  is_default: boolean;
  created_by: string | null;
  created_by_name: string | null;
  created_at: string;
  updated_at: string;
}

export interface DatasetCreateData {
  name: string;
  description?: string;
  database_type: string;
  schema_sql: string;
  seed_sql?: string;
}

export interface DatasetPreviewResult {
  success?: boolean;
  columns?: string[];
  rows?: unknown[][];
  row_count?: number;
  affected_rows?: number;
  execution_time_ms?: number;
  error_message?: string;
}

const datasetsApi = {
  list: async (): Promise<Dataset[]> => {
    const response = await apiClient.get<Dataset[]>('/datasets/');
    return response.data;
  },

  get: async (id: string): Promise<Dataset> => {
    const response = await apiClient.get<Dataset>(`/datasets/${id}/`);
    return response.data;
  },

  create: async (data: DatasetCreateData): Promise<Dataset> => {
    const response = await apiClient.post<Dataset>('/datasets/', data);
    return response.data;
  },

  update: async (id: string, data: Partial<DatasetCreateData>): Promise<Dataset> => {
    const response = await apiClient.patch<Dataset>(`/datasets/${id}/`, data);
    return response.data;
  },

  delete: async (id: string): Promise<void> => {
    await apiClient.delete(`/datasets/${id}/`);
  },

  uploadSql: async (file: File): Promise<{ schema_sql: string; seed_sql: string }> => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await apiClient.post<{ schema_sql: string; seed_sql: string }>(
      '/datasets/upload_sql/',
      formData,
      { headers: { 'Content-Type': 'multipart/form-data' } }
    );
    return response.data;
  },

  preview: async (id: string, query?: string): Promise<DatasetPreviewResult> => {
    const response = await apiClient.post<DatasetPreviewResult>(
      `/datasets/${id}/preview/`,
      query ? { query } : {}
    );
    return response.data;
  },

  generate: async (params: {
    topic: string;
    size: 'small' | 'medium' | 'large';
    database_type: string;
  }): Promise<{ name: string; description: string; schema_sql: string; seed_sql: string }> => {
    const response = await apiClient.post('/datasets/generate/', params);
    return response.data;
  },
};

export default datasetsApi;
