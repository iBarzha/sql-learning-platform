import { useCallback, useRef, useState } from 'react';

interface FileUploadProps {
  onUpload: (file: File) => void;
  isUploading?: boolean;
  maxSizeMB?: number;
  accept?: string;
}

const FILE_TYPE_ICONS: Record<string, string> = {
  pdf: '📄',
  image: '🖼️',
  code: '💻',
  other: '📎',
};

export function getFileTypeIcon(fileType: string): string {
  return FILE_TYPE_ICONS[fileType] || FILE_TYPE_ICONS.other;
}

export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function FileUpload({
  onUpload,
  isUploading = false,
  maxSizeMB = 10,
  accept,
}: FileUploadProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);
  const [error, setError] = useState('');

  const handleFile = useCallback(
    (file: File) => {
      setError('');
      if (file.size > maxSizeMB * 1024 * 1024) {
        setError(`File too large. Maximum size is ${maxSizeMB}MB.`);
        return;
      }
      onUpload(file);
    },
    [onUpload, maxSizeMB],
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      if (e.dataTransfer.files.length > 1) {
        setError('Only one file can be uploaded at a time.');
        return;
      }
      const file = e.dataTransfer.files[0];
      if (file) handleFile(file);
    },
    [handleFile],
  );

  const handleChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) handleFile(file);
      if (inputRef.current) inputRef.current.value = '';
    },
    [handleFile],
  );

  return (
    <div>
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
        className={`border-2 border-dashed rounded-lg p-6 text-center cursor-pointer transition-colors ${
          dragOver
            ? 'border-blue-400 bg-blue-50'
            : 'border-gray-300 hover:border-gray-400'
        } ${isUploading ? 'opacity-50 pointer-events-none' : ''}`}
      >
        <input
          ref={inputRef}
          type="file"
          className="hidden"
          onChange={handleChange}
          accept={accept}
        />
        {isUploading ? (
          <p className="text-sm text-gray-500">Uploading...</p>
        ) : (
          <>
            <p className="text-sm text-gray-600">
              Drop file here or click to browse
            </p>
            <p className="text-xs text-gray-400 mt-1">
              Max {maxSizeMB}MB
            </p>
          </>
        )}
      </div>
      {error && <p className="text-sm text-red-600 mt-1">{error}</p>}
    </div>
  );
}
