import { useQuery } from '@tanstack/react-query';
import sandboxApi from '@/api/sandbox';

export function useDatabaseTypes() {
  return useQuery({
    queryKey: ['sandbox', 'database-types'],
    queryFn: () => sandboxApi.getDatabaseTypes(),
    staleTime: Infinity,
  });
}

export function useSandboxDatasets(databaseType?: string) {
  return useQuery({
    queryKey: ['sandbox', 'datasets', databaseType],
    queryFn: () => sandboxApi.getDatasets(databaseType),
    enabled: !!databaseType,
  });
}
