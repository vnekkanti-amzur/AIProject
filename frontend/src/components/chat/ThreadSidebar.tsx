import { useState, useRef, useEffect } from 'react';
import type { Thread } from '../../types';

interface ThreadSidebarProps {
  threads: Thread[];
  activeThreadId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
  onRename: (id: string, title: string) => void;
  onDelete: (id: string) => void;
}

export function ThreadSidebar({ threads, activeThreadId, onSelect, onNew, onRename, onDelete }: ThreadSidebarProps) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editValue, setEditValue] = useState('');
  const [menuOpenId, setMenuOpenId] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (editingId && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [editingId]);

  const startRename = (t: Thread) => {
    setMenuOpenId(null);
    setEditingId(t.id);
    setEditValue(t.title);
  };

  const commitRename = (id: string) => {
    const trimmed = editValue.trim();
    if (trimmed) onRename(id, trimmed);
    setEditingId(null);
  };

  return (
    <aside className="w-64 border-r border-slate-200 dark:border-slate-800 flex flex-col">
      <button
        onClick={onNew}
        className="m-3 rounded-md bg-blue-600 hover:bg-blue-700 text-white px-3 py-2"
      >
        New chat
      </button>
      <ul className="flex-1 overflow-y-auto">
        {threads.map((t) => (
          <li key={t.id} className="relative group">
            {editingId === t.id ? (
              <input
                ref={inputRef}
                value={editValue}
                onChange={(e) => setEditValue(e.target.value)}
                onBlur={() => commitRename(t.id)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') commitRename(t.id);
                  if (e.key === 'Escape') setEditingId(null);
                }}
                className="w-full px-3 py-2 text-sm bg-slate-100 dark:bg-slate-800 outline-none border border-blue-400 rounded"
              />
            ) : (
              <div className="flex items-center">
                <button
                  onClick={() => onSelect(t.id)}
                  className={
                    'flex-1 text-left px-3 py-2 text-sm truncate ' +
                    (t.id === activeThreadId
                      ? 'bg-slate-100 dark:bg-slate-800'
                      : 'hover:bg-slate-50 dark:hover:bg-slate-900')
                  }
                >
                  {t.title}
                </button>
                <div className="relative">
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      setMenuOpenId(menuOpenId === t.id ? null : t.id);
                    }}
                    className="px-2 py-2 text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 opacity-0 group-hover:opacity-100 focus:opacity-100"
                    title="Thread options"
                  >
                    ⋯
                  </button>
                  {menuOpenId === t.id && (
                    <div className="absolute right-0 z-10 w-32 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded shadow-md">
                      <button
                        onClick={() => startRename(t)}
                        className="w-full text-left px-3 py-2 text-sm hover:bg-slate-100 dark:hover:bg-slate-700"
                      >
                        Rename
                      </button>
                      <button
                        onClick={() => {
                          setMenuOpenId(null);
                          onDelete(t.id);
                        }}
                        className="w-full text-left px-3 py-2 text-sm text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20"
                      >
                        Delete
                      </button>
                    </div>
                  )}
                </div>
              </div>
            )}
          </li>
        ))}
      </ul>
    </aside>
  );
}
