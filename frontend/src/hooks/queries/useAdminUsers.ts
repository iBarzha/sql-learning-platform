import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { adminApi, type AdminCreateUserData, type AdminUpdateUserData } from '@/api/auth';

export const ADMIN_USERS_KEY = ['admin-users'] as const;

export function useAdminUsers(params: {
  role?: string;
  search?: string;
  page?: number;
  page_size?: number;
}) {
  return useQuery({
    queryKey: [...ADMIN_USERS_KEY, params],
    queryFn: () => adminApi.listUsers(params),
  });
}

export function useAvailableCourses() {
  return useQuery({
    queryKey: ['admin-available-courses'],
    queryFn: () => adminApi.listAvailableCourses(),
  });
}

function useInvalidateUsers() {
  const qc = useQueryClient();
  return () => qc.invalidateQueries({ queryKey: ADMIN_USERS_KEY });
}

export function useCreateUser() {
  const invalidate = useInvalidateUsers();
  return useMutation({
    mutationFn: (data: AdminCreateUserData) => adminApi.createUser(data),
    onSuccess: invalidate,
  });
}

export function useUpdateUser() {
  const invalidate = useInvalidateUsers();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: AdminUpdateUserData }) =>
      adminApi.updateUser(id, data),
    onSuccess: invalidate,
  });
}

export function useResetUserPassword() {
  const invalidate = useInvalidateUsers();
  return useMutation({
    mutationFn: (id: string) => adminApi.resetPassword(id),
    onSuccess: invalidate,
  });
}

export function useDeleteUser() {
  const invalidate = useInvalidateUsers();
  return useMutation({
    mutationFn: (id: string) => adminApi.deleteUser(id),
    onSuccess: invalidate,
  });
}
