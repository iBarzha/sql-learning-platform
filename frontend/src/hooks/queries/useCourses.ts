import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import coursesApi, { type CreateCourseData, type UpdateCourseData } from '@/api/courses';

export function useCourses(params?: { search?: string; is_published?: boolean }) {
  return useQuery({
    queryKey: ['courses', params],
    queryFn: () => coursesApi.list(params),
  });
}

export function useCourse(id: string | undefined) {
  return useQuery({
    queryKey: ['course', id],
    queryFn: () => coursesApi.get(id!),
    enabled: !!id,
  });
}

export function useMyEnrollments() {
  return useQuery({
    queryKey: ['enrollments', 'my'],
    queryFn: () => coursesApi.getMyEnrollments(),
  });
}

export function useCourseEnrollments(courseId: string | undefined) {
  return useQuery({
    queryKey: ['course', courseId, 'enrollments'],
    queryFn: () => coursesApi.getEnrollments(courseId!),
    enabled: !!courseId,
  });
}

export function useCourseDatasets(courseId: string | undefined) {
  return useQuery({
    queryKey: ['course', courseId, 'datasets'],
    queryFn: () => coursesApi.getDatasets(courseId!),
    enabled: !!courseId,
  });
}

export function useCreateCourse() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: CreateCourseData) => coursesApi.create(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['courses'] });
    },
  });
}

export function useUpdateCourse(courseId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: UpdateCourseData) => coursesApi.update(courseId, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['courses'] });
      qc.invalidateQueries({ queryKey: ['course', courseId] });
    },
  });
}

export function useEnrollCourse(courseId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (enrollmentKey?: string) => coursesApi.enroll(courseId, enrollmentKey),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['course', courseId] });
      qc.invalidateQueries({ queryKey: ['courses'] });
      qc.invalidateQueries({ queryKey: ['enrollments'] });
    },
  });
}

export function useUnenrollCourse(courseId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => coursesApi.unenroll(courseId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['course', courseId] });
      qc.invalidateQueries({ queryKey: ['courses'] });
      qc.invalidateQueries({ queryKey: ['enrollments'] });
    },
  });
}

export function useDuplicateCourse() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ courseId, title }: { courseId: string; title?: string }) =>
      coursesApi.duplicate(courseId, title),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['courses'] });
    },
  });
}
