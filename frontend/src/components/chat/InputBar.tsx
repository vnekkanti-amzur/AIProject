import { useState, type FormEvent } from 'react';

interface InputBarProps {
  onSend: (text: string, files: File[]) => void;
  disabled?: boolean;
}

type AttachmentKind = 'image' | 'table' | 'formula' | 'code';

interface PendingAttachment {
  id: string;
  file: File;
  kind: AttachmentKind;
  previewUrl: string | null;
}

const ACCEPTED_EXTENSIONS = new Set([
  '.png',
  '.jpg',
  '.jpeg',
  '.csv',
  '.py',
  '.js',
  '.tex',
]);

const ACCEPT_ATTR = '.png,.jpg,.jpeg,.csv,.py,.js,.tex';

function extensionOf(name: string): string {
  const index = name.lastIndexOf('.');
  return index >= 0 ? name.slice(index).toLowerCase() : '';
}

function kindForExtension(ext: string): AttachmentKind {
  if (ext === '.png' || ext === '.jpg' || ext === '.jpeg') return 'image';
  if (ext === '.csv') return 'table';
  if (ext === '.tex') return 'formula';
  return 'code';
}

function kindBadgeLabel(kind: AttachmentKind): string {
  if (kind === 'table') return 'TABLE';
  if (kind === 'formula') return 'FORMULA';
  if (kind === 'code') return 'CODE';
  return 'IMG';
}

export function InputBar({ onSend, disabled }: InputBarProps) {
  const [text, setText] = useState('');
  const [attachments, setAttachments] = useState<PendingAttachment[]>([]);
  const [error, setError] = useState<string | null>(null);

  const addFiles = (fileList: FileList | null) => {
    if (!fileList || fileList.length === 0) return;

    const next: PendingAttachment[] = [];
    setError(null);
    for (const file of Array.from(fileList)) {
      const ext = extensionOf(file.name);
      if (!ACCEPTED_EXTENSIONS.has(ext)) {
        setError('Allowed attachments: PNG/JPG images, CSV tables, TEX formulas, PY/JS code.');
        continue;
      }

      const kind = kindForExtension(ext);
      next.push({
        id: crypto.randomUUID(),
        file,
        kind,
        previewUrl: kind === 'image' ? URL.createObjectURL(file) : null,
      });
    }

    if (next.length > 0) {
      setAttachments((prev) => [...prev, ...next]);
    }
  };

  const removeAttachment = (id: string) => {
    setAttachments((prev) => {
      const target = prev.find((item) => item.id === id);
      if (target?.previewUrl) {
        URL.revokeObjectURL(target.previewUrl);
      }
      return prev.filter((item) => item.id !== id);
    });
  };

  const clearAttachments = () => {
    setAttachments((prev) => {
      prev.forEach((item) => {
        if (item.previewUrl) {
          URL.revokeObjectURL(item.previewUrl);
        }
      });
      return [];
    });
  };

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const value = text.trim();
    if (!value && attachments.length === 0) return;
    onSend(value, attachments.map((item) => item.file));
    setText('');
    clearAttachments();
  };

  return (
    <form
      onSubmit={submit}
      className="border-t border-slate-200 dark:border-slate-800 p-3"
    >
      {attachments.length > 0 && (
        <div className="mb-2 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {attachments.map((item) => (
            <div
              key={item.id}
              className="flex items-center gap-2 rounded-md border border-slate-200 dark:border-slate-700 p-2"
            >
              {item.kind === 'image' && item.previewUrl ? (
                <img
                  src={item.previewUrl}
                  alt={item.file.name}
                  className="h-12 w-12 rounded object-cover"
                />
              ) : (
                <div className="flex h-12 w-12 items-center justify-center rounded border border-slate-300 text-[10px] font-semibold text-slate-600 dark:border-slate-600 dark:text-slate-300">
                  {kindBadgeLabel(item.kind)}
                </div>
              )}
              <div className="min-w-0 flex-1">
                <p className="truncate text-xs font-medium">{item.file.name}</p>
                <p className="text-[11px] text-slate-500">{kindBadgeLabel(item.kind)}</p>
              </div>
              <button
                type="button"
                onClick={() => removeAttachment(item.id)}
                className="rounded border border-slate-300 px-2 py-1 text-[11px]"
              >
                Remove
              </button>
            </div>
          ))}
        </div>
      )}

      <div className="flex gap-2">
        <label className="cursor-pointer rounded-md border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 px-3 py-2 text-sm">
          <input
            type="file"
            className="hidden"
            multiple
            accept={ACCEPT_ATTR}
            disabled={disabled}
            onChange={(e) => {
              addFiles(e.target.files);
              e.currentTarget.value = '';
            }}
          />
          Attach
        </label>
        <input
          type="text"
          value={text}
          onChange={(e) => setText(e.target.value)}
          disabled={disabled}
          placeholder="Ask about text or attachments..."
          className="flex-1 rounded-md border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 px-3 py-2"
        />
        <button
          type="submit"
          disabled={disabled}
          className="rounded-md bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 disabled:opacity-50"
        >
          Send
        </button>
      </div>

      {error && <p className="mt-2 text-xs text-red-600">{error}</p>}
    </form>
  );
}
