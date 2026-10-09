import { useQuery } from '@tanstack/react-query';
import gradingApi from '@/api/grading';

export function useCriteriaCatalog() {
  return useQuery({
    queryKey: ['grading', 'criteria'],
    queryFn: gradingApi.getCriteriaCatalog,
    staleTime: Infinity,
  });
}
