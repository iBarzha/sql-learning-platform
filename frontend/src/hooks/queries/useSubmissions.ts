import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import submissionsApi, { type SubmitQueryData } from '@/api/submissions';
import type { ManualScoreData } from '@/types';

export function useMySubmissions(courseId: string | undefined, assignmentId: string | undefined) {
  return useQuery({
    queryKey: ['assignment', courseId, assignmentId, 'submissions', 'my'],
    queryFn: () => submissionsApi.getMySubmissions(courseId!, assignmentId!),
    enabled: !!courseId && !!assignmentId,
  });
}

export function useSubmitAssignment(courseId: string, assignmentId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: SubmitQueryData) => submissionsApi.submit(courseId, assignmentId, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['assignment', courseId, assignmentId, 'submissions'] });
    },
  });
}

export function useMyProgress() {
  return useQuery({
    queryKey: ['progress', 'my'],
    queryFn: () => submissionsApi.getMyProgress(),
  });
}

export function useCourseProgress(courseId: string | undefined) {
  return useQuery({
    queryKey: ['course', courseId, 'progress'],
    queryFn: () => submissionsApi.getCourseProgress(courseId!),
    enabled: !!courseId,
  });
}

export function useMyResults(courseId: string | undefined) {
  return useQuery({
    queryKey: ['course', courseId, 'results', 'my'],
    queryFn: () => submissionsApi.getMyResults(courseId!),
    enabled: !!courseId,
  });
}

export function useStudentResults(courseId: string | undefined, studentId: string | undefined) {
  return useQuery({
    queryKey: ['results', { course: courseId, student: studentId }],
    queryFn: () => submissionsApi.listResults({ course: courseId, student: studentId }),
    enabled: !!courseId && !!studentId,
  });
}

export function useLessonResults(lessonId: string | undefined) {
  return useQuery({
    queryKey: ['results', { lesson: lessonId }],
    queryFn: () => submissionsApi.listResults({ lesson: lessonId }),
    enabled: !!lessonId,
  });
}

export function useSetManualScore() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ resultId, data }: { resultId: string; data: ManualScoreData }) =>
      submissionsApi.setManualScore(resultId, data),
    onSuccess: (result) => {
      qc.invalidateQueries({ queryKey: ['results'] });
      qc.invalidateQueries({ queryKey: ['student', result.student, 'progress'] });
    },
  });
}

export function useStudentProgress(studentId: string | undefined) {
  return useQuery({
    queryKey: ['student', studentId, 'progress'],
    queryFn: () => submissionsApi.getStudentProgress(studentId!),
    enabled: !!studentId,
  });
}
