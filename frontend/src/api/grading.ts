import apiClient from './client';
import type { CriterionInfo } from '@/types';

const gradingApi = {
  getCriteriaCatalog: async () => {
    const response = await apiClient.get<CriterionInfo[]>('/grading/criteria/');
    return response.data;
  },
};

export default gradingApi;
