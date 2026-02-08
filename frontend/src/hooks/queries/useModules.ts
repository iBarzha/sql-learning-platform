import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import modulesApi, { type CreateModuleData, type UpdateModuleData } from '@/api/modules';

export function useModules(courseId: string | undefined) {
  return useQuery({
    queryKey: ['course', courseId, 'modules'],
    queryFn: () => modulesApi.list(courseId!),
    enabled: !!courseId,
  });
}

export function useCreateModule(courseId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: CreateModuleData) => modulesApi.create(courseId, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['course', courseId, 'modules'] });
    },
  });
}

export function useUpdateModule(courseId: string, moduleId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: UpdateModuleData) =>
      modulesApi.update(courseId, moduleId, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['course', courseId, 'modules'] });
    },
  });
}

export function useDeleteModule(courseId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (moduleId: string) => modulesApi.delete(courseId, moduleId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['course', courseId, 'modules'] });
    },
  });
}
