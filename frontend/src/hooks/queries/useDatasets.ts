import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import datasetsApi, { type DatasetCreateData } from '@/api/datasets';

export function useMyDatasets() {
  return useQuery({
    queryKey: ['datasets', 'mine'],
    queryFn: () => datasetsApi.list(),
  });
}

export function useDataset(id: string | undefined) {
  return useQuery({
    queryKey: ['dataset', id],
    queryFn: () => datasetsApi.get(id!),
    enabled: !!id,
  });
}

export function useCreateDataset() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: DatasetCreateData) => datasetsApi.create(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['datasets', 'mine'] });
    },
  });
}

export function useUpdateDataset(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: Partial<DatasetCreateData>) => datasetsApi.update(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['datasets', 'mine'] });
      qc.invalidateQueries({ queryKey: ['dataset', id] });
    },
  });
}

export function useDeleteDataset() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => datasetsApi.delete(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['datasets', 'mine'] });
    },
  });
}
