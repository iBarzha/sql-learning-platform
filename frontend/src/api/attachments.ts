import apiClient from './client';

export interface Attachment {
  id: string;
  lesson: string | null;
  assignment: string | null;
  file: string;
  filename: string;
  file_type: string;
  file_size: number;
  uploaded_by: string;
  uploaded_by_name: string;
  download_url: string;
  created_at: string;
}

export const attachmentsApi = {
  list: async (courseId: string, lessonId: string): Promise<Attachment[]> => {
    const response = await apiClient.get(
      `/courses/${courseId}/lessons/${lessonId}/attachments/`,
    );
    return response.data;
  },

  upload: async (
    courseId: string,
    lessonId: string,
    file: File,
  ): Promise<Attachment> => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await apiClient.post(
      `/courses/${courseId}/lessons/${lessonId}/attachments/`,
      formData,
      { headers: { 'Content-Type': 'multipart/form-data' } },
    );
    return response.data;
  },

  delete: async (
    courseId: string,
    lessonId: string,
    attachmentId: string,
  ): Promise<void> => {
    await apiClient.delete(
      `/courses/${courseId}/lessons/${lessonId}/attachments/${attachmentId}/`,
    );
  },
};
