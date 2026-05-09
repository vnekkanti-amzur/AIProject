import { useEffect, useMemo, useState } from 'react';
import { uploadAttachments } from '../../lib/api';
import type { UploadedAttachment } from '../../types';

interface LocalAttachment {
  id: string;
  file: File;
  previewUrl: string | null;
  category: 'image' | 'document' | 'code';
}

interface AttachmentUploadProps {
  disabled?: boolean;
  onUploaded?: (files: UploadedAttachment[]) => void;
}

const ACCEPTED_EXTENSIONS = new Set(['.png', '.jpg', '.jpeg', '.pdf', '.csv', '.py', '.js']);

function getExtension(name: string): string {
  const idx = name.lastIndexOf('.');
  return idx >= 0 ? name.slice(idx).toLowerCase() : '';
}

function getCategoryByExtension(ext: string): 'image' | 'document' | 'code' {
  if (ext === '.png' || ext === '.jpg' || ext === '.jpeg') return 'image';
  if (ext === '.pdf' || ext === '.csv') return 'document';
  return 'code';
}

function formatSize(sizeBytes: number): string {
  if (sizeBytes < 1024) return `${sizeBytes} B`;
  if (sizeBytes < 1024 * 1024) return `${(sizeBytes / 1024).toFixed(1)} KB`;
  return `${(sizeBytes / (1024 * 1024)).toFixed(1)} MB`;
}

function FileTypeIcon({ category }: { category: 'image' | 'document' | 'code' }) {
  const label = category === 'document' ? 'DOC' : category === 'code' ? 'CODE' : 'IMG';
  const colorClass =
    category === 'document'
      ? 'bg-amber-100 text-amber-700 border-amber-300'
      : category === 'code'
        ? 'bg-emerald-100 text-emerald-700 border-emerald-300'
        : 'bg-blue-100 text-blue-700 border-blue-300';

  return (
    <div className={`flex h-16 w-16 items-center justify-center rounded-lg border text-xs font-semibold ${colorClass}`}>
      {label}
    </div>
  );
}

export function AttachmentUpload({ disabled, onUploaded }: AttachmentUploadProps) {
  const [pendingFiles, setPendingFiles] = useState<LocalAttachment[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);

  useEffect(() => {
    return () => {
      pendingFiles.forEach((item) => {
        if (item.previewUrl) URL.revokeObjectURL(item.previewUrl);
      });
    };
  }, [pendingFiles]);

  const accept = useMemo(() => '.png,.jpg,.jpeg,.pdf,.csv,.py,.js', []);

  const addFiles = (fileList: FileList | null) => {
    if (!fileList || fileList.length === 0) return;

    setError(null);
    const next: LocalAttachment[] = [];

    Array.from(fileList).forEach((file) => {
      const ext = getExtension(file.name);
      if (!ACCEPTED_EXTENSIONS.has(ext)) {
        setError('Only PNG/JPG, PDF/CSV, and .py/.js files are allowed.');
        return;
      }

      const category = getCategoryByExtension(ext);
      const previewUrl = category === 'image' ? URL.createObjectURL(file) : null;
      next.push({
        id: crypto.randomUUID(),
        file,
        previewUrl,
        category,
      });
    });

    if (next.length > 0) {
      setPendingFiles((prev) => [...prev, ...next]);
    }
  };

  const removeFile = (id: string) => {
    setPendingFiles((prev) => {
      const found = prev.find((item) => item.id === id);
      if (found?.previewUrl) URL.revokeObjectURL(found.previewUrl);
      return prev.filter((item) => item.id !== id);
    });
  };

  const clearAll = () => {
    setPendingFiles((prev) => {
      prev.forEach((item) => {
        if (item.previewUrl) URL.revokeObjectURL(item.previewUrl);
      });
      return [];
    });
  };

  const upload = async () => {
    if (pendingFiles.length === 0 || isUploading) return;

    setIsUploading(true);
    setError(null);
    try {
      const uploaded = await uploadAttachments(pendingFiles.map((item) => item.file));
      clearAll();
      onUploaded?.(uploaded);
    } catch {
      setError('Upload failed. Please try again.');
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <section className="border-t border-slate-200 dark:border-slate-800 px-3 pt-3">
      <div className="flex items-center gap-3">
        <label className="cursor-pointer rounded-md border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 px-3 py-2 text-sm">
          <input
            type="file"
            className="hidden"
            multiple
            accept={accept}
            disabled={disabled || isUploading}
            onChange={(e) => {
              addFiles(e.target.files);
              e.currentTarget.value = '';
            }}
          />
          Attach Files
        </label>
        <button
          type="button"
          onClick={upload}
          disabled={disabled || isUploading || pendingFiles.length === 0}
          className="rounded-md bg-slate-900 text-white dark:bg-slate-200 dark:text-slate-900 px-3 py-2 text-sm disabled:opacity-50"
        >
          {isUploading ? 'Uploading...' : 'Upload'}
        </button>
        <button
          type="button"
          onClick={clearAll}
          disabled={disabled || isUploading || pendingFiles.length === 0}
          className="rounded-md border border-slate-300 dark:border-slate-700 px-3 py-2 text-sm disabled:opacity-50"
        >
          Clear
        </button>
      </div>

      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}

      {pendingFiles.length > 0 && (
        <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {pendingFiles.map((item) => (
            <article
              key={item.id}
              className="flex items-center gap-3 rounded-lg border border-slate-200 dark:border-slate-700 p-2"
            >
              {item.category === 'image' && item.previewUrl ? (
                <img
                  src={item.previewUrl}
                  alt={item.file.name}
                  className="h-16 w-16 rounded-lg object-cover"
                />
              ) : (
                <FileTypeIcon category={item.category} />
              )}
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium">{item.file.name}</p>
                <p className="text-xs text-slate-500">{formatSize(item.file.size)}</p>
              </div>
              <button
                type="button"
                onClick={() => removeFile(item.id)}
                className="rounded border border-slate-300 dark:border-slate-700 px-2 py-1 text-xs"
              >
                Remove
              </button>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
