import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { attachmentsApi } from '../../api/attachments';

export function useAttachments(courseId?: string, lessonId?: string) {
  return useQuery({
    queryKey: ['attachments', courseId, lessonId],
    queryFn: () => attachmentsApi.list(courseId!, lessonId!),
    enabled: !!courseId && !!lessonId,
  });
}

export function useUploadAttachment(courseId: string, lessonId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (file: File) => attachmentsApi.upload(courseId, lessonId, file),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['attachments', courseId, lessonId] });
    },
  });
}

export function useDeleteAttachment(courseId: string, lessonId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (attachmentId: string) =>
      attachmentsApi.delete(courseId, lessonId, attachmentId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['attachments', courseId, lessonId] });
    },
  });
}
