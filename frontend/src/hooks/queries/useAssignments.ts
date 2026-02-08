import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import assignmentsApi from '@/api/assignments';

export function useAssignments(courseId: string | undefined) {
  return useQuery({
    queryKey: ['course', courseId, 'assignments'],
    queryFn: () => assignmentsApi.list(courseId!),
    enabled: !!courseId,
  });
}

export function useAssignment(courseId: string | undefined, assignmentId: string | undefined) {
  return useQuery({
    queryKey: ['assignment', courseId, assignmentId],
    queryFn: () => assignmentsApi.get(courseId!, assignmentId!),
    enabled: !!courseId && !!assignmentId,
  });
}

export function useDeleteAssignment(courseId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (assignmentId: string) => assignmentsApi.delete(courseId, assignmentId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['course', courseId, 'assignments'] });
    },
  });
}
