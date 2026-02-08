import apiClient from './client';

export interface Module {
  id: string;
  title: string;
  description: string;
  order: number;
  lesson_count: number;
  is_published: boolean;
  created_at: string;
  updated_at?: string;
}

export interface CreateModuleData {
  title: string;
  description?: string;
  order?: number;
  is_published?: boolean;
}

export type UpdateModuleData = Partial<CreateModuleData>;

const modulesApi = {
  list: async (courseId: string) => {
    const response = await apiClient.get<Module[]>(
      `/courses/${courseId}/modules/`
    );
    return response.data;
  },

  get: async (courseId: string, id: string) => {
    const response = await apiClient.get<Module>(
      `/courses/${courseId}/modules/${id}/`
    );
    return response.data;
  },

  create: async (courseId: string, data: CreateModuleData) => {
    const response = await apiClient.post<Module>(
      `/courses/${courseId}/modules/`,
      data
    );
    return response.data;
  },

  update: async (courseId: string, id: string, data: UpdateModuleData) => {
    const response = await apiClient.patch<Module>(
      `/courses/${courseId}/modules/${id}/`,
      data
    );
    return response.data;
  },

  delete: async (courseId: string, id: string) => {
    await apiClient.delete(`/courses/${courseId}/modules/${id}/`);
  },

  reorder: async (courseId: string, moduleIds: string[]) => {
    const response = await apiClient.post(
      `/courses/${courseId}/modules/reorder/`,
      { module_ids: moduleIds }
    );
    return response.data;
  },
};

export default modulesApi;
