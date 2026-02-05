import { apiClient } from './client';

export interface DatabaseType {
  value: string;
  label: string;
  description: string;
}

export interface SandboxDataset {
  id: string;
  name: string;
  description: string;
  course_title: string;
  database_type: string;
  schema_sql: string;
  seed_sql: string;
}

export interface ExecuteQueryRequest {
  database_type: string;
  query: string;
  schema_sql?: string;
  seed_sql?: string;
  dataset_id?: string;
}

export interface QueryResult {
  success: boolean;
  columns?: string[];
  rows?: unknown[][];
  row_count?: number;
  affected_rows?: number;
  execution_time_ms: number;
  error_message?: string;
}

const sandboxApi = {
  getDatabaseTypes: async (): Promise<DatabaseType[]> => {
    const response = await apiClient.get('/sandbox/database-types/');
    return response.data;
  },

  getDatasets: async (databaseType?: string): Promise<SandboxDataset[]> => {
    const params = databaseType ? { database_type: databaseType } : {};
    const response = await apiClient.get('/sandbox/datasets/', { params });
    return response.data;
  },

  executeQuery: async (request: ExecuteQueryRequest): Promise<QueryResult> => {
    const response = await apiClient.post('/sandbox/execute/', request);
    return response.data;
  },
};

export default sandboxApi;
