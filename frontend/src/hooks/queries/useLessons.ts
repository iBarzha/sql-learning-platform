import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import lessonsApi, { type CreateLessonData, type UpdateLessonData } from '@/api/lessons';

export function useLessons(courseId: string | undefined) {
  return useQuery({
    queryKey: ['course', courseId, 'lessons'],
    queryFn: () => lessonsApi.list(courseId!),
    enabled: !!courseId,
  });
}

export function useLesson(courseId: string | undefined, lessonId: string | undefined) {
  return useQuery({
    queryKey: ['lesson', courseId, lessonId],
    queryFn: () => lessonsApi.get(courseId!, lessonId!),
    enabled: !!courseId && !!lessonId,
  });
}

export function useLessonSubmissions(courseId: string | undefined, lessonId: string | undefined) {
  return useQuery({
    queryKey: ['lesson', courseId, lessonId, 'submissions'],
    queryFn: () => lessonsApi.getMySubmissions(courseId!, lessonId!),
    enabled: !!courseId && !!lessonId,
  });
}

export function useCreateLesson(courseId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: CreateLessonData) => lessonsApi.create(courseId, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['course', courseId, 'lessons'] });
    },
  });
}

export function useUpdateLesson(courseId: string, lessonId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: UpdateLessonData) => lessonsApi.update(courseId, lessonId, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['course', courseId, 'lessons'] });
      qc.invalidateQueries({ queryKey: ['lesson', courseId, lessonId] });
    },
  });
}

export function useDeleteLesson(courseId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (lessonId: string) => lessonsApi.delete(courseId, lessonId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['course', courseId, 'lessons'] });
    },
  });
}

export function useSubmitLesson(courseId: string, lessonId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (query: string) => lessonsApi.submit(courseId, lessonId, query),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['lesson', courseId, lessonId, 'submissions'] });
      qc.invalidateQueries({ queryKey: ['lesson', courseId, lessonId] });
    },
  });
}
